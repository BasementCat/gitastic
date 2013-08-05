import os
import multiconfig
import database

configDir=os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")
configName="gitastic"
config=None

def init():
	global config
	config=multiconfig.getConfig(configName, os.path.join(configDir, "base.yaml"))
	testing_config=os.path.join(configDir, "testing_config.yml")
	if os.path.exists(testing_config):
		config.load(testing_config)
	database.connect()

def getWebHost():
	global config
	return config.get("Web/FallbackHost", default="localhost")