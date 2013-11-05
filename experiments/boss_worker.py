#!/usr/bin/env python
"""
    Experiment running Python code in a subprocess.
    This runs a minimal, ugly Python shell on the command line,
        with all the work done in a worker subprocess.
    The worker keeps the Python globals, imported modules,
        and defined functions and classes between tasks.
    Output can show up in dribs and drabs with pauses between.
    Stdout and stderr streams are multiplexed through a pipe and
    come out the terminal's stdout and stderr respectively.
    Outputs are buffered, with flushing both at newlines and
        when the interpreted code calls flush() "manually".
    ^C from the keyboard is caught and relayed to the worker
        by calling os.kill(worker.pid, signal.SIGINT).
    Tracebacks are printed for exceptions and ^C.

    This file contains both the boss- and worker-side code.
    See worker_test and middle_manager_test, below,
    for illustrative tasks to give the worker.

    Copyright (c) 2013 Steve Witham All rights reserved.  
    PyInThePhone is available under a BSD license, whose full text is at:
        https://github.com/switham/pyinthephone/blob/master/LICENSE
    
"""

import sys
import os
import ast
import traceback
import multiprocessing
import time
import signal
import errno
from pty import STDIN_FILENO, STDOUT_FILENO, STDERR_FILENO


def stdin_readlines(task_filename):
    """
    Get list of \n-terminated lines from stdin,
    terminated by a blank line or end of file.
    """
    if task_filename:
        print >>sys.stderr, "=====", task_filename, "====="
    sys.stderr.flush()
    lines = []
    # "for line in sys.stdin" has buffering which causes problems.
    while True:
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            if lines:
                print >>sys.stderr, "\nClearing input."
                lines = []
                continue

            else:
                raise
        if not line:
            # i.e., end of file
            break

        if line == '\n':
            # Blank line signals end of input (easier on Android).
            break

        lines.append(line)
    return lines


class Fd_pipe_wrapper():
    """
    Wrapper to redirect an output stream into a multiprocessing.Connection
    pipe-end, in such a way that it can be multiplexed with other output
    streams.
    As in:
        stdout = Fd_pipe_wrapper(conn, STDOUT_FILENO)
        stderr = Fd_pipe_wrapper(conn, STDERR_FILENO)
        print >>stdout, "Output to stdout."
        print >>stderr, "Message to stderr."
        conn.send({"eof": True})
        
    Uses a convention of sending dictionaries like this through the pipe:
        {"eof": False, "fd": 0, "str": "Output to stdout.\n"}
    Each call to a wrapper's write() method produces one of these; in general
    each is just a chunk of text, not necessarily a whole or single line.
    Deciding whether and where to put newlines is up to the caller, although
    print statements (as above) insert them automatically.
    Decoding where lines end is up to the code at the other end of the pipe.
    
    To signal that the fds have closed (all together), code outside this
    class should do this:
        conn.send({"eof": True})
    This is not sent by the wrappers' close() method, on the theory that
    there are multple streams to close, but only one eof message should
    be sent to close them all together.
    
    There is no code in this class to interpret the sent dictionaries at the
    other end of the pipe.
    
    Thanks to ibell at http://stackoverflow.com/questions/11129414
    """
    def __init__(self, connection, fd):
        self.conn = connection
        self.fd = fd

    def __repr__(self):
        return "Fd_pipe_wrapper(%r, %d)" % (self.conn, self.fd)
        
    def write(self, text):
        self.conn.send({"eof": False, "fd": self.fd, "text": text})
        
    def flush(self):
        """
        This class does no buffering of its own,
        but see the Tty_buffer class.
        """
        pass
    
    def close(self):
        """ See Fd_pipe_wrapper top docstring about how to signal EOF. """
        pass


class Tty_buffer(object):
    """
    Do buffering for a file-like object the way the stdout does
    when connected to a terminal, i.e., flush on newlines.
    """
    def __init__(self, file_like_object, buffsize=2048):
        self.file = file_like_object
        self.buffsize = buffsize
        self.buffer = ""

    def __repr__(self):
        return "Tty_buffer(%r, buffsize=%d)" % (self.file, self.buffsize)

    def write(self, string):
        self.buffer += string
        if len(self.buffer) >= self.buffsize:
            self.flush()
        else:
            p = string.rfind('\n')
            if p > -1:
                # Flush up to the (last) newline.
                p = p - len(string) + len(self.buffer)
                self.file.write(self.buffer[:p + 1])
                self.file.flush()
                self.buffer = self.buffer[p + 1:]

    def flush(self):
        if self.buffer:
            self.file.write(self.buffer)
            self.buffer = ""
        self.file.flush()

    def close(self):
        self.flush()
    

def worker_main(worker_conn):
    """
    Within the worker process, this is the "target" function that is run.
    It's the Python read-eval-print loop within the worker.
    It has a globals dictionary that persists between code_string tasks.
    worker_conn is the worker's end of the boss <-> worker pipe.
    """
    worker_globals = {}
    code_cache = {}
    stdout = Tty_buffer(Fd_pipe_wrapper(worker_conn, STDOUT_FILENO))
    stderr = Tty_buffer(Fd_pipe_wrapper(worker_conn, STDERR_FILENO))
    stdin = open("/dev/null", "r")
    while True:
        task = worker_conn.recv()
        if not task["do_run"]:
            break

        code_filename = task["code_filename"]
        code_string = task["code_string"]
        code_cache[code_filename] = code_string.splitlines()
        interpret(code_string, worker_globals,
                  stdin, stdout, stderr,
                  code_filename,
                  code_cache)
        stdout.flush()
        stderr.flush()
        worker_conn.send({"eof": True})


def worker_print_exc(limit=None, file=sys.stderr,
                     code_filename=None, code_cache={}):
    """
    Like traceback.print_exc(), except:
    1) Print traceback starting with the first entry about code_filename
       (which in our case will be a string like "<input 17>").
    2) For lines in current or previous tasks (rather than imported modules),
       include the appropriate line's text from code_cache.
       (print_exc() etc. can only fetch lines from actual files.)
    """
    if code_filename == None:
        traceback.print_exc(limit, file)
        return

    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb = traceback.extract_tb(exc_traceback)
    for i, entry in enumerate(tb):
        if entry[0] == code_filename:
            tb = tb[i:]
            break
    else:
        tb = []
    if limit != None:
        tb = tb[:min(len(tb), limit)]
    if tb:
        print >>file, "Traceback (most recent call last):"
        for i, (filename, line_no, fn_name, text) in enumerate(tb):
            if text == None and filename in code_cache:
                text = code_cache[filename][line_no - 1].strip()
                tb[i] = (filename, line_no, fn_name, text)
        file.write("".join(traceback.format_list(tb)))
    file.write("".join(traceback.format_exception_only(exc_type, exc_value)))


def interpret(code_string, worker_globals, stdin, stdout, stderr,
              code_filename, code_cache):
    """
    Parse the (multi-line) Python code_string, then exec it
        using the given globals dict,
        and with the given stdio file-like objects.
    If the last line in code_string is an expression, print its value.
    Print stack traces from exceptions, including ^C/KeyboardInterrupt/SIGINT.
    """
    saved_stdin = sys.stdin
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
        
    sys.stdin = stdin
    sys.stdout = stdout
    sys.stderr = stderr
    try:
        tree = ast.parse(code_string, code_filename)
        code1 = code2 = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_line = ast.Interactive(tree.body[-1:])
            tree.body = tree.body[:-1]
            code2 = compile(last_line, code_filename, "single")
        if tree.body:
            code1 = compile(tree, code_filename, "exec")

        if code1:
            exec code1 in worker_globals
        if code2:
            exec code2 in worker_globals
    except:
        print >>sys.stdout  # Flush and newline.
        worker_print_exc(None, sys.stderr, code_filename, code_cache)
    finally:
        sys.stdin = saved_stdin
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr


def worker_test():
    """
    A test to run within the worker.  This lets you see...
      o  output appearing gradually (worker sleeps between prints)
      o  forced (flush()) and automatic (newline) flushing of stdout
      o  how the system responds to ^C.
    You can get the worker to run this by saying
        from boss_worker import *
        worker_test()
    """
    print "I am worker pid", os.getpid()
    for i in range(10):
        for j in range(10):
            print i * 10 + j,
            time.sleep(.1)
            if i < 5:
                # The first five lines flush every number printed.
                sys.stdout.flush()
        # All lines flush at the newline.
        print


def middle_manager_test(level=1):
    """
    A test to run within the worker.  The worker becomes a boss to
    another worker, tells the subworker to run worker_test (above), and
    makes comments before and after.  This shows output and ^C (if you like)
    being relayed two steps.

    Not really an essential feature but once I thought of it I had to do it.

    You can get the worker to run this by saying
        from boss_worker import *
        middle_manager_test()
    """
    print "I am level", level, "middle-manager pid", os.getpid()
    print "- - -"
    if level <= 1:
        task = "worker_test()"
    else:
        task = "middle_manager_test(%d)" % (level - 1)
    boss_main("from boss_worker import *\n" + task)
    print "I am pid %d, tired of level %d management." % (os.getpid(), level)


def boss_main(initial_task=None):
    """
    The main loop for the boss.
    Set up one worker multiprocessing.Process connected with a two-way pipe.
    Do the boss side of a Python read-eval-print loop, where
        "read" means get multi-line input from the terminal, ended with a
             blank line (blank line alone means quit.)
        "eval" means send input to worker, which evals and sends outputs back,
        "print" outputs as they come back, till the worker says it's done.
    Handle ^C by just relaying it to the worker to interrupt the current task.
        (a second ^C kills the worker and quits entirely).
    """
    boss_conn, worker_conn = multiprocessing.Pipe()
    worker = multiprocessing.Process(target=worker_main, args=(worker_conn,))
    worker.start()

    # Detach worker from boss's process group so it doesn't receive the ^C
    # from the keyboard, but only indirectly from interrupt_worker() below.
    os.setpgid(worker.pid, worker.pid)
    try:
        if initial_task:
            print initial_task
            oversee_one_task(initial_task, worker, boss_conn,
                             task_filename="<command-line>")
        else:        
            n = 1
            while True:
                task_filename = "<input %d>" % n
                task_string = "".join(stdin_readlines(task_filename))
                if not task_string:
                    break

                oversee_one_task(task_string, worker, boss_conn,
                                 task_filename)
                n += 1
        boss_conn.send({"do_run": False})
        worker.join()
    except KeyboardInterrupt:
        # Normally ^C is caught in oversee_one_task().  We catch it here
        # only if the user hits ^C a second time, or in an unexpected place.
        # That means trouble; make sure the worker is cleaned up.
        os.kill(worker.pid, signal.SIGKILL)


DEFAULT_SIGINT_HANDLER = signal.getsignal(signal.SIGINT)


def oversee_one_task(task_string, worker, boss_conn,
                     task_filename):
    """" Give the worker one task, echo the results, and handle ^C. """
    
    def interrupt_worker(sig_num, stack_frame):
        os.kill(worker.pid, signal.SIGINT)
        # If there's another ^C, interrupt the boss (this process).
        signal.signal(signal.SIGINT, DEFAULT_SIGINT_HANDLER)

    print "-----"
    signal.signal(signal.SIGINT, interrupt_worker)
    boss_conn.send({"do_run": True,
                    "code_string": task_string,
                    "code_filename": task_filename,
                    })
    while True:
        try:
            # If ^C is hit, it's likely to be while boss_conn.recv() is
            # blocked waiting for output from the worker.
            chunk = boss_conn.recv()
            if chunk["eof"]:
                break

            fd, text = chunk["fd"], chunk["text"]
            if fd == STDOUT_FILENO:
                sys.stdout.write(text)
                sys.stdout.flush()
            elif fd == STDERR_FILENO:
                sys.stderr.write(text)
                sys.stderr.flush()
            else:
                sys.stderr.write(" FILENO %d? " % fd)
                sys.stderr.flush()
                
        # Python normally handles both SIGINT itself, and an EINTR that comes
        # out of a blocked system call immediately after, with one exception:
        # KeyboardInterrupt.  interrupt_worker() catches the SIGINT;
        # here is where we deal with (ignore) the EINTR.
        except IOError as (code, msg):
            if code == errno.EINTR:
                continue
            else:
                raise

    signal.signal(signal.SIGINT, DEFAULT_SIGINT_HANDLER)


if __name__ == "__main__":
    boss_main(" ".join(sys.argv[1:]))
