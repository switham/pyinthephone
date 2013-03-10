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

if __name__ == "__main__":
    files = argv[1:] + wsgi_demo.TYPICAL_FILES_TO_SERVE
    wsgi_demo.serve(*files, public=False, python=True)
