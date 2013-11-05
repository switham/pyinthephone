#!/usr/bin/env python
""" 
ajax.py -- experiment doing AJAX requests and modifying the DOM.

    Copyright (c) 2013 Steve Witham All rights reserved.  
    PyInThePhone is available under a BSD license, whose full text is at:
        https://github.com/switham/pyinthephone/blob/master/LICENSE
"""

from bottle import route, run
from bottle import static_file
import os


@route("/")
def ajax():
    return static_file("ajax.html", os.getcwd())


COUNTER = 0

@route("/more", method="ANY")
def more():
    global COUNTER

    n = 16
    result = ["<br>[%d]: uvwxyz\n" % c for c in range(COUNTER, COUNTER + n)]
    COUNTER += n
    return result



@route("/clear", method="POST")
def clear():
    global COUNTER
    
    COUNTER = 0
    return ""


run(host="localhost", port=8765, debug=True)
    
