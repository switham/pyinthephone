#!/usr/bin/env python
""" run_worker.py -- Experiment running python code in a subprocess. """

from sys import stdin
import sys
import ast
import traceback
import StringIO


def get_input_string():
    lines = []
    try:
        # "for line in stdin" has buffering which causes problems.
        while True:
            line = stdin.readline()
            if not line:
                break
            
            lines += line
    except KeyboardInterrupt:
        pass
    return "".join(lines)


def unixify_newlines(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')


NOTEBOOK_GLOBALS = {}

def interpret(code_string):
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    output = StringIO.StringIO()
    trace = ""
    try:
        sys.stdout = output
        sys.stderr = output
        
        tree = ast.parse(code_string, "<your input>")
        code1 = code2 = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_line = ast.Interactive(tree.body[-1:])
            tree.body = tree.body[:-1]
            code2 = compile(last_line, "<your input>", "single")
        if tree.body:
            code1 = compile(tree, "<your input>", "exec")

        if code1:
            exec code1 in NOTEBOOK_GLOBALS
        if code2:
            exec code2 in NOTEBOOK_GLOBALS
    except Exception, KeyboardInterrupt:
        trace = traceback.format_exc()
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
    return unixify_newlines(output.getvalue()), unixify_newlines(trace)


if __name__ == "__main__":
    while True:
        input_string = get_input_string()
        if not input_string:
            break

        print "-----"
        response, trace = interpret(input_string)
        if response:
            print response,
        if trace:
            print trace,
        print "====="
