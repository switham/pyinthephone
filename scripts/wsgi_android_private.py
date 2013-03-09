#!/usr/bin/env python
"""
wsgi_android_private.py--wsgi_demo.py serving its source + Python on 127.0.0.1.
The Python interpreter is turned on.  Serves on loopback/localhost only.
This gets the options into wsgi_demo on Android.

RUN FROM THE wsgi_demo directory: scripts/wsgi_self_serv.py
The wsgi_demo directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.
"""

from sys import argv
from glob import glob

import wsgi_demo

class Args(object):
    pass

if __name__ == "__main__":
    args = Args()
    args.public = False
    args.port = 8000
    args.python = True
    args.files = [
        "scripts/wsgi_demo.py",
        "scripts/wsgi_self_serv.py",
        "data/SL4A2.jpg",
        ] + glob("scripts/wsgi_android_*.py")
    # "data/foo.zip",
    # "data/foo.txt",
    # "data/SL4A.jpg",
    wsgi_demo.serve(args)
