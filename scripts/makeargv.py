#!/usr/bin/env python
"""
Allow Unix or Python-style args to a program.

A way to make these three equivalent (assuming optparse is set up):

program("--quiet", "--port", "8000", "file1.c", "file2.c", "3.14")
program("file1.c", "file2.c", 3.14, quiet=True, verbose=False, port=8000)
program(*argv[1:])

The beginning of program() looks like this (again assuming optparse setup):

def program(*pargs, **kargs):
    argv = makeargv.make_argv(*pargs, **kargs)
    options, args = parser.parse_args(argv)
    ...

In the Python-style arguments case, makeargv.make_argv() creates a
Unix-argv-like list of string arguments, which is then processed
by optparse.  If only *argv[1:] is present, it is passed as-is.

This should work with optparse or argparse.  I'm testing with optparse
only because argparse wasn't available on my Android phone's Python
install.
"""

def make_argv(*pargs, **kargs):
    """
    Create an argv-like list of strings by converting the kargs
    option=value pairs to strings in the front of the returned list.
    Only double-hyphen option names are produced.
    Values to options can any type; all but True and False are passed
    through str():
        True and False:
            It's assumed that true/false options are "store_true", so:
                option=True => "--option".
                option=False => nothing.
        String values are left alone:
            file="foo.c" => "--file", "foo.c".
        Other types:
            port=-32767 => "--port, "-32767"  # Watch the minus sign.
            foo=None => "--foo", "None"
            files=["a", "b"] => "--files", '["a", "b"]'  # Sorry.
    Positional arguments are all passed through str(), so:
        *[True, None, 3.14] => "True", "None", "3.14".
    """
    opts = []
    for opt, value in kargs.iteritems():
        if value == False:
            continue
        
        opts.append("--" + opt)
        if value == True:
            continue

        opts.append(value)
    return [str(arg) for arg in opts + list(pargs)]


def __check_opts_args(options, args):
    try:
        if options.quiet == True \
            and options.verbose == False \
            and options.port == 8000 \
            and args == ["file1.c", "file2.c", "3.14"]:
            return "pass"
        else:
            return "FAIL"
    except:
        return "FAIL"
        

def __test_make_argv():
    global OptionParser
    from optparse import OptionParser

    O, A = __program("--quiet", "--port", "8000",
                     "file1.c", "file2.c", "3.14")
    print "String args:", __check_opts_args(O, A)

    O, A = __program("file1.c", "file2.c", 3.14,
                     quiet=True, verbose=False, port=8000)
    print "Python args:", __check_opts_args(O, A)

        
def __program(*pargs, **kargs):
    optparser = OptionParser()
    optparser.add_option("--quiet", action="store_true", default=False)
    optparser.add_option("--verbose", action="store_true", default=False)
    optparser.add_option("--port", type=int)

    return optparser.parse_args(make_argv(*pargs, **kargs))


if __name__ == "__main__":
    __test_make_argv()
