import bottle

app = bottle.Bottle()

if __name__ == '__main__':
    bottle.debug(True)
    bottle.run(app, server = 'wsgiref', host = '127.0.0.1', port = 8080, reloader = True, debug = True)