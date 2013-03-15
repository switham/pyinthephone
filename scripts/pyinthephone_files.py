#!/usr/bin/env python
"""
pyinthephone_files.py -- pyinthephone serving its source code ON PUBLIC IP.
The Python interpreter is turned off.
On Android, this gets the options into pyinthephone.

RUN FROM THE pyinthephone directory: scripts/pyinthephone_files.py
The pyinthephone directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.
"""

from sys import argv
from glob import glob

import pyinthephone

class Args(object):
    pass

if __name__ == "__main__":
    files = argv[1:] + pyinthephone.TYPICAL_FILES_TO_SERVE
    pyinthephone.serve(*files, public=True, python=False)
