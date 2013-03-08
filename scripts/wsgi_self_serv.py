#!/usr/bin/env python
"""
wsgi_self_serv.py -- wsgi_demo.py serving its source code.
RUN FROM THE wsgi_demo directory: scripts/wsgi_self_serv.py
The wsgi_demo directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.
"""

from wsgiref.simple_server import make_server
import os
from sys import argv, exit

from wsgi_demo import allow_files, app


if __name__ == "__main__":
    allow_files(["scripts/wsgi_demo.py", "scripts/wsgi_self_serv.py",
                 "data/SL4A2.jpg",
                 ])
                 # "data/foo.zip", "data/foo.txt",
                 # "data/SL4A.jpg",
    allow_files(argv[1:])
    httpd = make_server('', 8000, app)
    print "serving on port 8000"

    # Serve until process is killed
    httpd.serve_forever()
