#!/usr/bin/env python
""" run_worker.py -- Experiment running python code in a subprocess. """

from sys import stdin
import sys
import ast
import traceback
import StringIO
import multiprocessing


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


def be_worker(child_conn):
    worker_globals = {}
    while True:
        do_run, code_string = child_conn.recv()
        if not do_run:
            break

        response, trace = interpret(code_string, worker_globals)
        child_conn.send( (True, response, trace) )
        

def interpret(code_string, worker_globals):
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
            exec code1 in worker_globals
        if code2:
            exec code2 in worker_globals
    except Exception, KeyboardInterrupt:
        trace = traceback.format_exc()
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
    return unixify_newlines(output.getvalue()), unixify_newlines(trace)


if __name__ == "__main__":
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=be_worker, args=(child_conn,))
    p.start()

    while True:
        input_string = get_input_string()
        if not input_string:
            parent_conn.send( (False, "", "") )
            break

        print "-----"
        parent_conn.send( (True, input_string) )
        alive, response, trace = parent_conn.recv()
        if response:
            print response,
        if trace:
            print trace,
        print "====="
        if not alive:
            break
        
    print "Worker quitting..."
    p.join()
    print "Worker quit."
