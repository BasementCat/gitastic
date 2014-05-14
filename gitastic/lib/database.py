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
from datetime import datetime
from storm.locals import *
from storm.expr import *
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
    timestamp=DateTime()
    added_from_ip=Unicode(default=u"0.0.0.0")

    def __init__(self, **kwargs):
        self.timestamp=datetime.utcnow()
        super(UserSSHKey, self).__init__(**kwargs)

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

class Team(Model, FilesystemPathValidationMixin):
    ACC_SUPERADMIN=8
    ACC_ADMIN=4
    ACC_MODERATE=2
    ACC_VIEW=1
    ACC_NONE=0

    __storm_table__="team"
    team_id=Int(primary=True)
    name=Unicode(default=u"")
    description=Unicode()

    @classmethod
    def validateName(self, otherName):
        self._validateFilesystemPathComponent(value=otherName, message="Your desired team name contains invalid characters")

    def getAccess(self, other_user):
        acc=None
        try:
            acc=getStore().find(TeamMembership, And(TeamMembership.team==self, TeamMembership.user==other_user)).one()
        except NotOneError:
            return self.ACC_NONE
        return acc.access if acc else self.ACC_NONE

    def setAccess(self, other_user, access):
        if access not in (self.ACC_SUPERADMIN, self.ACC_ADMIN, self.ACC_MODERATE, self.ACC_VIEW, self.ACC_NONE):
            raise RepositoryError("Access must be a valid access level")
        getStore().find(TeamMembership, And(TeamMembership.team==self, TeamMembership.user==other_user)).remove()
        if access!=self.ACC_NONE:
            getStore().add(TeamMembership(team=self, user=other_user, access=access))
        getStore().commit()

class TeamMembership(Model):
    __storm_table__="team_membership"
    __storm_primary__=("team_id", "user_id")
    team_id=Int()
    team=Reference(team_id, Team.team_id)
    user_id=Int()
    user=Reference(user_id, User.user_id)
    access=Int()

class Repository(Model, FilesystemPathValidationMixin):
    ACC_OWNER=8
    ACC_ADMIN=4
    ACC_PUSH=2
    ACC_VIEW=1
    ACC_NONE=0

    PERM_ADMIN=ACC_OWNER|ACC_ADMIN
    PERM_PUSH=PERM_ADMIN|ACC_PUSH
    PERM_CLONE=PERM_PUSH|ACC_VIEW
    PERM_VIEW=PERM_CLONE

    __storm_table__="repository"
    repository_id=Int(primary=True)
    name=Unicode(default=u"")
    path=Unicode(default=u"")
    description=Unicode(default=u"")
    public=Bool(default=True)
    owner_user_id=Int()
    owner_user=Reference(owner_user_id, User.user_id)
    owner_team_id=Int()
    owner_team=Reference(owner_team_id, Team.team_id)

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
        #Teams take precedence over users
        return self.owner_team or self.owner_user

    def getOwnerName(self):
        owner=self.getOwner()
        if isinstance(owner, User):
            return owner.username
        elif isinstance(owner, Team):
            return owner.name
        raise RepositoryError("The owner of repository %s #%d does not exist"%(self.name, self.repository_id))

    def _getAccess(self, other_user):
        acc=None
        try:
            acc=getStore().find(RepositoryAccess, And(RepositoryAccess.repository==self, RepositoryAccess.user==other_user)).one()
        except NotOneError:
            return self.ACC_NONE
        return acc.access if acc else self.ACC_NONE

    def getAccess(self, other_user):
        owner=self.getOwner()
        access=self._getAccess(other_user)
        if isinstance(owner, Team):
            team_access=owner.getAccess(other_user)
            return max(
                self.ACC_OWNER if team_access==Team.ACC_SUPERADMIN else self.ACC_NONE,
                self.ACC_ADMIN if team_access==Team.ACC_ADMIN else self.ACC_NONE,
                self.ACC_PUSH if team_access==Team.ACC_MODERATE else self.ACC_NONE,
                self.ACC_VIEW if team_access==Team.ACC_VIEW else self.ACC_NONE,
                min(access, self.ACC_ADMIN),
                self.ACC_NONE
            )
        else:
            return max(
                self.ACC_OWNER if owner==other_user else self.ACC_NONE,
                access,
                self.ACC_VIEW if self.public else self.ACC_NONE,
                self.ACC_NONE
            )

    def setAccess(self, other_user, access):
        if access==self.ACC_OWNER:
            raise RepositoryError("Owner access must be set by changing the repository owner")
        elif access in (self.ACC_ADMIN, self.ACC_PUSH, self.ACC_VIEW, self.ACC_NONE):
            getStore().find(RepositoryAccess, And(RepositoryAccess.repository==self, RepositoryAccess.user==other_user)).remove()
            if access!=self.ACC_NONE:
                getStore().add(RepositoryAccess(repository=self, user=other_user, access=access))
            getStore().commit()
        else:
            raise RepositoryError("Access must be a valid access level")

    def _getRepositoryShortPath(self):
        return os.path.join(self.getOwnerName(), self.name+".git")

    def getRepositoryDir(self):
        repobase=gitastic.config.get("Repository/BaseDirectory", do_except=True)
        return os.path.join(repobase, self._getRepositoryShortPath())

    def getRepositoryCloneURI(self, proto="ssh"):
        if proto=="ssh":
            return "%s@%s:%s"%(
                pwd.getpwuid(os.getuid())[0],
                gitastic.getWebHost(),
                self._getRepositoryShortPath())
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
Team.repositories=ReferenceSet(Team.team_id, Repository.owner_team_id)

class RepositoryAccess(Model):
    __storm_table__="repository_access"
    __storm_primary__=("repository_id", "user_id")
    repository_id=Int()
    repository=Reference(repository_id, Repository.repository_id)
    user_id=Int()
    user=Reference(user_id, User.user_id)
    access=Int()