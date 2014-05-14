import bottle

from multiconfig import getConfig

from lib import models

conf = getConfig('lunchroom')
conf.load('config.yaml')

models.init()

app = bottle.Bottle()

if __name__ == '__main__':
    bottle.debug(True)
    bottle.run(app, server = 'wsgiref', host = '127.0.0.1', port = 8080, reloader = True, debug = True)