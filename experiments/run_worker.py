#!/usr/bin/env python
""" run_worker.py -- Experiment running python code in a subprocess. """

from sys import stdin
import sys
import os
import ast
import traceback
import StringIO
import multiprocessing
import time
import signal
import errno


def get_input_string():
    lines = []
    # "for line in stdin" has buffering which causes problems.
    while True:
        try:
            line = stdin.readline()
        except KeyboardInterrupt:
            if lines:
                print >>sys.stderr, "\nClearing input."
                lines = []
                continue

            else:
                raise
        if not line:
            break

        lines += line
    return "".join(lines)


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
    class can send:
        {"eof": True}
    This is not sent by the wrappers' close() method, on the theory that
    there are multple streams to close, but only one eof message should
    be sent to close them all together.
    
    There is no code in this class to interpret these dictionaries on the
    other end of the pipe.
    
    Thanks to ibell at http://stackoverflow.com/questions/11129414
    """
    def __init__(self, connection, fd, buffer_size=2048):
        self.conn = connection
        self.fd = fd
        
    def write(self, string):
        self.conn.send({"eof": False, "fd": self.fd, "str": string})
        
    def flush(self):
        # This class does no buffering of its own.
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
    

def be_worker(child_conn):
    worker_globals = {}
    while True:
        do_run, code_string = child_conn.recv()
        if not do_run:
            break

        stdout = Tty_buffer(Fd_pipe_wrapper(child_conn, 0))
        stderr = Tty_buffer(Fd_pipe_wrapper(child_conn, 1))
        interpret(code_string, worker_globals, stdout, stderr)
        stdout.flush()
        stderr.flush()
        child_conn.send({"eof": True})


def interpret(code_string, worker_globals, stdout, stderr):
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
        sys.stdout.flush()
        sys.stdout = saved_stdout
        sys.stderr.flush()
        sys.stderr = saved_stderr


def test_flush():
    """
    Test how automatic and forced flushing work for stdout.
    You can get the worker to run this by saying
        from run_worker import test_Flush
        test_flush()
    """
    for i in range(10):
        for j in range(10):
            print i * 10 + j,
            time.sleep(.1)
            if i < 5:
                # The first five lines flush every number printed.
                sys.stdout.flush()
        # All lines flush at the newline.
        print


if __name__ == "__main__":
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=be_worker, args=(child_conn,))
    p.start()

    # Detach child from parent process group so it doesn't receive
    # the ^C from the keyboard, but only indirectly from interrupt_p() below.
    os.setpgid(p.pid, p.pid)
    default_intr = signal.getsignal(signal.SIGINT)
    try:
        while True:
            input_string = get_input_string()
            if not input_string:
                break

            print "-----"

            def interrupt_p(sig_num, stack_frame):
                os.kill(p.pid, signal.SIGINT)
                # If there's another ^C, interrupt the parent (this process).
                signal.signal(signal.SIGINT, default_intr)

            signal.signal(signal.SIGINT, interrupt_p)
            parent_conn.send( (True, input_string) )
            while True:
                try:
                    chunk = parent_conn.recv()
                    if chunk["eof"]:
                        break

                    sys.stdout.write(chunk["str"])
                    sys.stdout.flush()
                except IOError as (code, msg):
                    # Catch "interrupted system call" from ^C
                    # (during parent_conn.recv() above), and ignore.
                    if code == errno.EINTR:
                        continue

                    raise

            signal.signal(signal.SIGINT, default_intr)
            print "====="
        parent_conn.send( (False, "") )
        p.join()
    except KeyboardInterrupt:
        os.kill(p.pid, signal.SIGKILL)
