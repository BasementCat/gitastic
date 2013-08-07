import threading
import base64
import binascii
import struct
import tempfile
import shutil
import os
import pwd
import subprocess
import re
from storm.locals import *
from storm.exceptions import NotOneError
import bcrypt
import gitastic

class DatabaseError(Exception):
    pass

database=None
stores=dict()
stores_lock=threading.RLock()

def getStore():
    global database, stores, stores_lock
    if database is None:
        raise DatabaseError("The database connection has not yet been established")
    tid=threading.current_thread().ident
    stores_lock.acquire(blocking=1)
    if tid not in stores:
        stores[tid]=Store(database)
    stores_lock.release()
    return stores[tid]

def connect():
    global database
    if database is None:
        database=create_database(gitastic.config.get("DatabaseURI", do_except=True))

class Model(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

class ModelError(Exception):
    pass

class RepositoryError(ModelError):
    pass

class ValidationError(ModelError):
    pass

class FilesystemPathValidationMixin(object):
    @classmethod
    def _validateFilesystemPathComponent(self, value, message=None):
        if not re.match(ur"^[\w\d_-]+$", value):
            raise ValidationError(message or "validation failed")

class User(Model, FilesystemPathValidationMixin):
    __storm_table__="user"
    user_id=Int(primary=True)
    username=Unicode(default=u"")
    email=Unicode(default=u"")
    password=Unicode(default=u"")

    def setPassword(self, newPassword):
        self.password=unicode(bcrypt.hashpw(newPassword, bcrypt.gensalt(gitastic.config.get("User/BcryptRounds", default=12))))

    def checkPassword(self, otherPassword):
        otherHash=bcrypt.hashpw(otherPassword, self.password)
        return otherHash==self.password

    @classmethod
    def authenticate(self, username, password):
        try:
            user=getStore().find(self, self.username.like(unicode(username))).one()
        except NotOneError:
            return None
        return user if user and user.checkPassword(password) else None

    @classmethod
    def validateUsername(self, otherUsername):
        self._validateFilesystemPathComponent(value=otherUsername, message="Your desired username contains invalid characters")

class UserSSHKey(Model):
    __storm_table__="user_ssh_key"
    user_ssh_key_id=Int(primary=True)
    user_id=Int()
    user=Reference(user_id, User.user_id)
    name=Unicode()
    key=Unicode()

    @staticmethod
    def validateKey(keystr):
        try:
            keyType, keyData_encoded, keyComment=keystr.split()
            keyData=base64.decodestring(keyData_encoded)
            if keyData=="":
                return False
        except ValueError:
            return False
        except binascii.Error:
            return False

        typeStrLen=struct.unpack(">I", keyData[:4])[0]
        typeStr=keyData[4:4+typeStrLen]
        return typeStr==keyType

User.keys=ReferenceSet(User.user_id, UserSSHKey.user_id)

class Repository(Model, FilesystemPathValidationMixin):
    ACC_OWNER=8
    ACC_ADMIN=4
    ACC_PUSH=2
    ACC_VIEW=1
    ACC_NONE=0

    __storm_table__="repository"
    repository_id=Int(primary=True)
    name=Unicode(default=u"")
    path=Unicode(default=u"")
    description=Unicode(default=u"")
    public=Bool(default=True)
    owner_user_id=Int()
    owner_user=Reference(owner_user_id, User.user_id)

    @classmethod
    def validateName(self, otherName):
        self._validateFilesystemPathComponent(value=otherName, message="Your desired repository name contains invalid characters")

    def setPath(self):
        self.path=unicode(u"/".join((self.getOwnerName(), self.name)))

    @classmethod
    def findByPath(self, path):
        repo=None
        try:
            repo=getStore().find(self, self.path==unicode(path[:-4] if path.endswith(".git") else path)).one()
        except NotOneError:
            pass
        return repo

    def getOwner(self):
        return self.owner_user

    def getOwnerName(self):
        owner=self.getOwner()
        if isinstance(owner, User):
            return owner.username
        raise RepositoryError("The owner of repository %s #%d does not exist"%(self.name, self.repository_id))

    def getAccess(self, other_user):
        owner=self.getOwner()
        if isinstance(owner, User) and owner==other_user:
            return self.ACC_OWNER
        elif self.public:
            return self.ACC_VIEW
        else:
            return self.ACC_NONE

    def getRepositoryDir(self):
        repobase=gitastic.config.get("Repository/BaseDirectory", do_except=True)
        return os.path.join(repobase, self.getOwnerName(), self.name+".git")

    def getRepositoryCloneURI(self, proto="ssh"):
        if proto=="ssh":
            return "%s@%s:%s/%s.git"%(
                pwd.getpwuid(os.getuid())[0],
                gitastic.getWebHost(),
                self.getOwnerName(),
                self.name)
        else:
            raise RepositoryError("Invalid clone protocol: %s"%(proto,))

    def create(self, add_readme=False):
        repodir=self.getRepositoryDir()
        if os.path.exists(repodir):
            raise RepositoryError("The repository directory already exists: %s"%(repodir,))
        try:
            os.makedirs(repodir)
            subprocess.check_call([gitastic.config.get("Repository/Git", do_except=True), "init", "--bare", repodir])
        except os.error as e:
            raise RepositoryError("The directory %s could not be created: %s"%(repodir, str(e)))
        except subprocess.CalledProcessError as e:
            raise RepositoryError("The repository %s could not be created: %s"%(repodir, str(e)))
        if add_readme:
            temp=tempfile.mkdtemp()
            checkout_dir=os.path.join(temp, self.getRepositoryDir().split("/").pop())
            readme=os.path.join(checkout_dir, "README.md")
            try:
                subprocess.check_call([
                    gitastic.config.get("Repository/Git", do_except=True),
                    "clone",
                    self.getRepositoryDir(),
                    checkout_dir])
                with open(readme, "w") as fp:
                    fp.write(u"# %s\n\n%s\n"%(self.name, self.description))
                curdir=os.getcwd()
                os.chdir(checkout_dir)
                subprocess.check_call([gitastic.config.get("Repository/Git", do_except=True), "add", readme])
                subprocess.check_call([gitastic.config.get("Repository/Git", do_except=True), "commit", "-m", "Initial commit"])
                subprocess.check_call([gitastic.config.get("Repository/Git", do_except=True), "push", "-u", "origin", "master"])
                os.chdir(curdir)
            except os.error as e:
                raise RepositoryError("Failed to create readme for %s: %s"%(self.getRepositoryDir(), str(e)))
            except subprocess.CalledProcessError as e:
                raise RepositoryError("Failed to create readme for %s: %s"%(self.getRepositoryDir(), str(e)))
            finally:
                shutil.rmtree(temp)

User.repositories=ReferenceSet(User.user_id, Repository.owner_user_id)