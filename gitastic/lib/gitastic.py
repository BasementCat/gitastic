import os
import multiconfig
import database

configDir=os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
configName="gitastic"
config=None

def init():
	global config
	config=multiconfig.getConfig(configName, os.path.join(configDir, "base.yaml"))
	database.connect()