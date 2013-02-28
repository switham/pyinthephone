#!/usr/bin/env python

from wsgiref.simple_server import make_server
import os

# Every WSGI application must have an application object - a callable
# object that accepts two arguments. For that purpose, we're going to
# use a function (note that you're not limited to a function, you can
# use a class for example). The first argument passed to the function
# is a dictionary containing CGI-style envrironment variables and the
# second variable is the callable object (see PEP 333).
def hello_world_app(environ, start_response):
    status = '200 OK' # HTTP Status
    headers = [('Content-type', 'text/plain')] # HTTP Headers
    start_response(status, headers)

    # The returned object is going to be printed
    return ["Welcome to " + os.path.abspath(__file__)]

httpd = make_server('', 8000, hello_world_app)
print "serving on port 8000"

# Serve until process is killed
httpd.serve_forever()
