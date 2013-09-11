#!/usr/bin/env python
""" ajax1.py """

from bottle import route, run
from bottle import static_file
import os


@route("/")
def ajax1():
    return static_file("ajax1.html", os.getcwd())


COUNTER = 0

@route("/more", method="POST")
def aaa():
    global COUNTER
    
    result ="<br>[%d]: uvwxyz" % COUNTER
    COUNTER += 1
    return result



@route("/clear", method="POST")
def aaa():
    global COUNTER
    
    COUNTER = 0
    return ""


run(host="localhost", port=8765, debug=True)
    
