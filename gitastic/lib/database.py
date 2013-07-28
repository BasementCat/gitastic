import threading
import base64
import binascii
import struct
from storm.locals import *
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
    database=create_database(gitastic.config.get("DatabaseURI", do_except=True))

class Model(object):
    def __init__(self, **kwargs):
        for k,v in kwargs.items():
            setattr(self, k, v)

class User(Model):
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