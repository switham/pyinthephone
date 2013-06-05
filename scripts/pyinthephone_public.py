#!/usr/bin/env python
"""
pyinthephone_public.py
    Copyright (c) 2013 Steve Witham All rights reserved.  
    PyInThePhone is available under a BSD two-clause license, whose
    full text can be found at http://github.com/switham/pyinthephone/LICENSE

pyinthephone serving source + PYTHON on PUBLIC IP.
The Python interpreter is turned on.  Serves on a PUBLIC IP address.
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
    pyinthephone.serve(*files, public=True, python=True)
