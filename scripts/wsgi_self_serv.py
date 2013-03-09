#!/usr/bin/env python
"""
wsgi_self_serv.py -- wsgi_demo.py serving its source code.
RUN FROM THE wsgi_demo directory: scripts/wsgi_self_serv.py
The wsgi_demo directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.
"""

from sys import argv
from glob import glob

import wsgi_demo


if __name__ == "__main__":
    wsgi_demo.allow_files([
        "scripts/wsgi_demo.py",
        "scripts/wsgi_self_serv.py",
        "data/SL4A2.jpg",
        ] + glob("scripts/wsgi_android_*.py")
        )
    # "data/foo.zip",
    # "data/foo.txt",
    # "data/SL4A.jpg",
    wsgi_demo.serve()
