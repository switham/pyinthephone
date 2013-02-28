#!/usr/bin/env python
""" wsgi_self_serv.py -- wsgi_demo.py serving its source code. """

from wsgiref.simple_server import make_server
import os
from sys import argv, exit

from wsgi_demo import allow_files, demo_app


if __name__ == "__main__":
    allow_files(["wsgi_demo.py", "wsgi_self_serv.py", "SL4A.jpg"])
    allow_files(argv[1:])
    httpd = make_server('', 8000, demo_app)
    print "serving on port 8000"

    # Serve until process is killed
    httpd.serve_forever()
