import threading
from storm.locals import *
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

# class User(Model):
# 	__storm_table__="user"
# 	user_id=Int(primary=True)