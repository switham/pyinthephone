#!/usr/bin/env python
"""
globals_exec.py -- Using a global environment with exec (or eval()).
Working up to making a Python shell in a browser.

This is my fix to the broken initial example at:
http://stackoverflow.com/questions/2904274/globals-and-locals-in-python-exec
(I'm user2117761 there because Google forced me to rename my Google account!)
"""

my_code = """
class A(object):
    pass

class B(object):
    a = A
"""

my_code_AST = compile(my_code, "My Code", "exec")
extra_global = "hi"
global_env = {}
exec my_code_AST in global_env
print "global_env.keys() =", global_env.keys()
print "B.a =", global_env["B"].a
