#!/usr/bin/env python
"""
    Experiment running Python code in a subprocess.
    This runs a Python shell (an ugly one) on the command line,
        but all the work is done in a worker subprocess.
    The worker keeps the Python globals, imported modules,
        and defined functions and classes between tasks.
    Output can show up in dribs and drabs with pauses between.
    Stdout and stderr streams are multiplexed through a pipe but
    distinguished.  (The difference isn't shown in this demo.)
    Outputs are buffered, with flushing both at newlines and
        when the interpreted code calls flush() "manually".
    ^C from the keyboard is caught and relayed to the worker
        by calling os.kill(worker.pid, signal.SIGINT).
    Tracebacks (overlong) are printed for exceptions and ^C.

    This file contains both the boss- and worker-side code.
    See worker_test and middle_manager_test, below,
    for illustrative tasks to give the worker.
"""

import sys
import os
import ast
import traceback
import multiprocessing
import time
import signal
import errno


def stdin_readlines():
    """ Get list of \n-terminated lines from stdin, terminated by ^D (EOF). """
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
            break

        lines.append(line)
    return lines


class Fd_pipe_wrapper():
    """
    Wrapper to redirect an output stream into a multiprocessing.Connection pipe-end,
    in such a way that it can be multiplexed with other output streams.
    As in:
        stdout = Fd_pipe_wrapper(conn, 0)
        stderr = Fd_pipe_wrapper(conn, 1)
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
    class, do this:
        conn.send({"eof": True})
    This is not sent by the wrappers' close() method, on the theory that
    there are multple streams to close, but only one eof message should
    be sent to close them all together.
    
    There is no code in this class to interpret the sent dictionaries ata the
    other end of the pipe.
    
    Thanks to ibell at http://stackoverflow.com/questions/11129414
    """
    def __init__(self, connection, fd, buffer_size=2048):
        self.conn = connection
        self.fd = fd
        
    def write(self, string):
        self.conn.send({"eof": False, "fd": self.fd, "str": string})
        
    def flush(self):
        # This class does no buffering of its own.  But see Tty_buffer below.
        pass
    
    def close(self):
        # See comments above about eof signalling.
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
    worker_conn is the worker's end of the boss-to-worker pipe.
    """
    worker_globals = {}
    while True:
        do_run, code_string = worker_conn.recv()
        if not do_run:
            break

        stdout = Tty_buffer(Fd_pipe_wrapper(worker_conn, 0))
        stderr = Tty_buffer(Fd_pipe_wrapper(worker_conn, 1))
        interpret(code_string, worker_globals, stdout, stderr)
        stdout.flush()
        stderr.flush()
        worker_conn.send({"eof": True})


def interpret(code_string, worker_globals, stdout, stderr):
    """
    Parse the (multi-line) Python code_string, then exec it
        using the given globals dict,
        and with the given stdout and stderr file-like objects.
    If the last line in code_string is an expression, print its value.
    Print stack traces from exceptions, including ^C/KeyboardInterrupt/SIGINT.
    """
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    try:
        sys.stdout = stdout
        sys.stderr = stderr
        
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
    except:
        print >>sys.stdout  # Flush and newline.
        sys.stderr.write(traceback.format_exc())  # Includes final newline.
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr


def worker_test():
    """
    A test to run within the worker.  This lets you see...
      o  output appearing gradually (worker sleeps between prints)
      o  automatic (newline) and forced (flush()) flushing of stdout
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
    another worker, tells subworker to run worker_test (above), and
    boasts during the process.

    This shows output and ^C (if you like) being relayed two steps.
    Not really an essential feature but once I thought of it...

    You can get the worker to run this by saying
        from boss_worker import *
        middle_manager_test()
    """
    print "I am level", level, "middle-manager pid", os.getpid()
    print "* * *"
    if level <= 1:
	task = "worker_test()"
    else:
        task = "middle_manager_test(%d)" % (level - 1)
    boss_main("from boss_worker import *\n" + task)
    print "*****"
    print "I am pid %d, tired of middle management." % os.getpid()
    print "***********"


def boss_main(initial_task=None):
    """
    The main loop for the boss.
    Set up one worker multiprocessing.Process connected with a two-way pipe.
    Do the boss side of a Python read-eval-print loop, where
        "read" means get multi-line input from the terminal, ended with ^D,
             (^D with no input means quit.)
        "eval" means send input to worker, which evals and sends outputs back,
        "print" outputs as they come back, till the worker says it's done.
    Handle ^C by just relaying it to the worker to interrupt the current task.
        (or a second ^C kills the worker and quits entirely).
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
	    oversee_one_task(initial_task, worker, boss_conn)
        while True:
            task_string = "".join(stdin_readlines())
            if not task_string:
                break

	    oversee_one_task(task_string, worker, boss_conn)
        boss_conn.send( (False, "") )
        worker.join()
    except KeyboardInterrupt:
        os.kill(worker.pid, signal.SIGKILL)
	

DEFAULT_SIGINT_HANDLER = signal.getsignal(signal.SIGINT)


def oversee_one_task(task_string, worker, boss_conn):
    """" Give the worker one task, echo the results, and handle ^C. """
    
    def interrupt_worker(sig_num, stack_frame):
	os.kill(worker.pid, signal.SIGINT)
	# If there's another ^C, interrupt the boss (this process).
	signal.signal(signal.SIGINT, DEFAULT_SIGINT_HANDLER)

    print "-----"
    signal.signal(signal.SIGINT, interrupt_worker)
    boss_conn.send( (True, task_string) )
    while True:
	try:
	    chunk = boss_conn.recv()
	    if chunk["eof"]:
		break

	    sys.stdout.write(chunk["str"])
	    sys.stdout.flush()
	except IOError as (code, msg):
	    # Catch "interrupted system call" from ^C
	    # during boss_conn.recv() above, and ignore.
	    if code == errno.EINTR:
		continue

	    raise

    signal.signal(signal.SIGINT, DEFAULT_SIGINT_HANDLER)
    print "====="


if __name__ == "__main__":
    boss_main(" ".join(sys.argv[1:]))
