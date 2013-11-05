#!/usr/bin/env python
"""
pyinthephone_private.py
    Copyright (c) 2013 Steve Witham All rights reserved.  
    PyInThePhone is available under a BSD license, whose full text is at:
        https://github.com/switham/pyinthephone/blob/master/README

pyinthephone serving source + Python on 127.0.0.1.
The Python interpreter is turned on.  Serves on loopback/localhost only.
On Android, this gets the options into pyinthephone.

RUN FROM THE pyinthephone directory: scripts/wsgi_self_serv.py
The pyinthephone directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.
"""

from sys import argv
from glob import glob

import pyinthephone

if __name__ == "__main__":
    files = argv[1:] + pyinthephone.TYPICAL_FILES_TO_SERVE
    pyinthephone.serve(*files, public=False, python=True)
