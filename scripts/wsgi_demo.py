#!/usr/bin/env python
"""
wsgi_demo.py--WSGI server with templating, a routing decorator, and some demos.
Based on wsgiref.simple_server
    and the example code at http://docs.python.org/2/library/wsgiref.html

Run this from the wsgi_demo directory like this:
    scripts/wsgi_demo.py [files...]
The wsgi_demo directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.

Arguments on the command line name files users are allowed to view & download.
(Paths are relative to the Python working dir, not the scripts directory.)

This code is insecure!
    It runs on your public IP address instead of 127.0.0.1.
    It displays at least one Unix environment variable (PWD).
    It shows Python stack traces on the python and 404 pages.
    It runs any Python code you give it.
    Besides python, it may be vulnerable to code-injection attacts
        (although I made some vain gestures).
    wsgi_self_serv.py makes this script display its own source code.
"""

from wsgiref.simple_server import make_server
import os
from sys import argv, exit, stderr
import sys
from mimetypes import guess_type
import cgi
import traceback
import StringIO
import ast


REQUIRED_ENV_VARS = [
    "PATH_INFO",
    "REQUEST_METHOD",
    "QUERY_STRING",
    "wsgi.input",
    "CONTENT_LENGTH",
    ]

INTERESTING_ENV_VARS = [
    "SERVER_PROTOCOL",
    "SERVER_SOFTWARE",
    "SERVER_NAME",
    "REMOTE_ADDR",
    "PATH_INFO_MATCHED",
    "PATH_INFO_TAIL",
    "SERVER_PORT",
    "HTTP_HOST",
    "HTTP_USER_AGENT",
    "PWD",
    "REMOTE_HOST",
    ]


header_template = """<!DOCTYPE html>
<html>

<head>
<title>%(title)s</title>
</head>

<body>
<p/>
<a href="/" style="font-size: small">home</a> &nbsp; &nbsp; &nbsp;
<a href="/environ" style="font-size: small">environ</a> &nbsp; &nbsp; &nbsp;
<a href="/download" style="font-size: small">files</a> &nbsp; &nbsp; &nbsp;
<a href="/python#input" style="font-size: small">python</a>
<p/>
<p/>
"""

trailer_template = """
</body>
</html>
"""

def html_header(environ, title=None):
    title = title or environ["PATH_INFO"]
    return [fill_template(header_template, locals())]


def html_trailer(environ):
    return [fill_template(trailer_template, locals())]


class HTML_safe_dict(object):
    """
    An instance of this class forms a dict-like wrapper around 1 or 2 dicts.
    If the element requested is in safe_dict:
        an html-safe, string version of the element is returned.
        These safe outputs have their quotation marks escaped
        so that they can be used within html attribute strings.
    else if the element is in raw_dict:
        the unchanged element of raw_dict is returned.

    This is not suitable for URL query parameters.
    """
    def __init__(self, safe_dict, raw_dict={}):
        assert isinstance(safe_dict, dict)
        assert isinstance(raw_dict, dict)
        self.safe_dict = safe_dict
        self.raw_dict = raw_dict

    def __getitem__(self, key):
        if key in self.safe_dict:
            return cgi.escape(str(self.safe_dict[key]), True)
        else:
            return self.raw_dict[key]


def fill_template(template, safe_dict, raw_dict={}):
    """
    If dict contains, e.g., "A": "foo", then
    "%(A)s" in template will be replaced by "foo".
    See HTML_safe_dict above for treatment of safe_dict and raw_dict elements.
    """
    return template % HTML_safe_dict(safe_dict, raw_dict)
    

ROUTES = {}

def route(path_pattern):
    """
    path_pattern should either
       start with "/" and end with "/*" --wildcard match-- or
       start with "/" but not include "*" --exact match.
    Pattern of use:
       @route("/")
       @route("/index.html")
       def home_page(environ, start_response):
           # home_page(), the handler, will have an environ including
           # PATH_INFO, PATH_INFO_MATCHED, and PATH_INFO_TAIL; see
           # match_route(), below.
           ...
           return text
    Matches (e.g. /foo/* matches /foo/bar) are tried most-specific-first;
        "/foo" is different from "/foo/";
        "/foo/" is more specific than "/foo/*".
    Exact, directory-like routes (e.g. @route("/foo/")) match the same string
    without the trailing slash, but not vice-versa, e.g.,
        @route("/foo/") matches /foo/ or /foo, but
        @route("/foo") only matches /foo.
    If you set up *different* routes for the same path_pattern except the
    last slash, results are undefined.
    """

    assert path_pattern.startswith("/")
    assert path_pattern.endswith("/*") or "*" not in path_pattern
    if path_pattern.endswith("/*"):
        assert "*" not in path_pattern[:-1]
    
    def route_setter(handler):
        ROUTES[path_pattern] = handler
        if path_pattern.endswith("/") and path_pattern != "/":
            # If, e.g., "/foo/", also match "/foo".
            ROUTES[path_pattern[:-1]] = handler
        return handler  # Unchanged.

    return route_setter


ALLOWED_FILES = set()

def allow_files(files):
    for file in files:
        assert file != ""
        ALLOWED_FILES.add(file)


def do_404(environ, start_response, complaint=None):
    do_headers(start_response, "404 NOT FOUND", "text/plain")
    chunks = ["%r not found.\n" % environ["PATH_INFO"]]
    if complaint:
        chunks.append("\nOr maybe it's this:\n\n" + complaint + "\n")

    return chunks


def match_route(path):
    """
    Match path to the appropriate handler callable in the ROUTES table.
    If found:
        return handler, matched, tail.
        # matched is the part of PATH_INFO that matched the pattern in
        #     an @route(), up to but not including any trailing '*'.
        # tail is whatever matched a trailing '*', or else an empty string.
    else:
        return None, None, None
    """
    assert "*" not in path, "'*' in path."
    assert "//" not in path, "'//' in path."
    
    parts = path.split("/")
    assert ".." not in parts, "'..' is a no-no."
    assert parts and parts[0] == '', "path should start with /"

    if path in ROUTES:  # All exact matches are caught here.
        return ROUTES[path], path, ""

    for n in range(len(parts) - 1, 0, -1):
        if parts[n] == "":  # foo/ should not match foo/* below.
            continue

        subpath = "/".join(parts[:n]) + "/"
        if path.startswith(subpath):
            wildpath = subpath + "*"
            if wildpath in ROUTES:
                return ROUTES[wildpath], subpath, "/".join(parts[n:])

    return None, None, None


def do_route(environ, start_response):
    """
    Route the request to the appropriate handler callable in the ROUTES table.
    Pass the handler an environ dict with "PATH_INFO_MATCHED" and
    "PATH_INFO_TAIL" entries added, corresponding to "matched" and "tail"
    from match_route().
    """
    handler, matched, tail = match_route(environ["PATH_INFO"])
    if not handler:
        return do_404(environ, start_response)

    handler_environ = dict(environ)
    handler_environ["PATH_INFO_MATCHED"] = matched
    handler_environ["PATH_INFO_TAIL"] = tail
    return handler(handler_environ, start_response)


def just_guess_type(filename):
    return guess_type(filename)[0]


def do_headers(start_response, status, content_type, *more):
    headers = []
    if content_type:
        headers.append( ('Content-Type', content_type) )
    headers += list(more)
    start_response(status, headers)


# Every WSGI application must have an application object - a callable
# object that accepts two arguments. For that purpose, we're going to
# use a function (note that you're not limited to a function, you can
# use a class for example). The first argument passed to the function
# is a dictionary containing CGI-style envrironment variables and the
# second variable is the callable object (see PEP 333).
def app(environ, start_response):
    try:
        environ = dict( (key, environ[key])
                        for key in REQUIRED_ENV_VARS + INTERESTING_ENV_VARS
                        if key in environ )
        chunks = do_route(environ, start_response)
        if environ["REQUEST_METHOD"] == "HEAD":
            # I am not going to try to return the correct Content-Length.
            return []

        return chunks
    except KeyboardInterrupt:
        exit(1)
        
    except Exception, e:
        return do_404(environ, start_response,
                      complaint=traceback.format_exc())


@route("/")
@route("/home/")
@route("/index.html")
@route("/welcome.html")
def home_page(environ, start_response):
    chunks = html_header(environ, title="WSGI Demo--Welcome!")
    chunks += ["Welcome to the script at\n" + os.path.abspath(__file__)]
    chunks += html_trailer(environ)
    do_headers(start_response, "200 OK", "text/html")
    return chunks


@route("/favicon.ico")
def icon(environ, start_response):
    actual_file_path = "data/SL4A2.jpg"
    contents = file(actual_file_path).read()
    do_headers(start_response, "200 OK", just_guess_type(actual_file_path))
    return [contents]



@route("/environ/")
@route("/environ/*")
def dump_environ(environ, start_response):
    chunks = html_header(environ, title="WSGI Demo--Welcome!")

    chunks += ['<pre style="word-wrap:break-word;">\n']
    chunks += ["os.getcwd(): " + os.getcwd() + "\n\n"]
    keys = sorted(environ.keys())
    chunks += ["%s: %r\n" % (key, environ[key]) for key in keys]
    chunks += ["</pre>\n"]
    
    chunks += html_trailer(environ)
    do_headers(start_response, "200 OK", "text/html")
    return chunks


@route("/static/")
@route("/download/")
def list_files(environ, start_response):
    chunks = html_header(environ, title="Static Files")

    chunks.append("<h3>Files available here:</h3>\n")
    fmt = """%s : <a href=%r>view</a>
                  <a href=%r>download</a><br>\n"""
    if ALLOWED_FILES:
        chunks += [fmt % (path, "/static/" + path, "/download/" + path)
                 for path in sorted(list(ALLOWED_FILES))]
    else:
        chunks.append("(none)<br>\n")

    chunks += html_trailer(environ)

    do_headers(start_response, "200 OK", "text/html")
    return chunks

    
@route("/static/*")
def do_static(environ, start_response):
    path = environ["PATH_INFO_TAIL"]
    assert not path.endswith("/"), \
        "I don't list directories under " + environ["PATH_INFO_MATCHED"]

    if path in ALLOWED_FILES:
        do_headers(start_response, "200 OK", just_guess_type(path))
        return [file(path).read()]
    else:
        return do_404(environ, start_response)


@route("/download/*")
def do_download(environ, start_response):
    path = environ["PATH_INFO_TAIL"]
    assert not path.endswith("/"), \
        "I don't list directories under " + environ["PATH_INFO_MATCHED"]

    if path in ALLOWED_FILES:
        download_path = os.path.basename(path)
        # download_path = download_path.replace("_", "")
        if os.path.splitext(download_path)[1] in [".py"]:
            download_path += ".txt"
        download_path = '"' + download_path + '"'
        do_headers(start_response, "200 OK", None,
                  ("Content-Disposition",
                    "attachment; filename=%s" % download_path),
                  ("Content-Type", "application/octet-stream"),
            )
        return [file(path).read()]
    else:
        return do_404(environ, start_response)


def get_POST_FieldStorage(environ):
    # cribbed from
    # http://stackoverflow.com/questions/530526/accessing-post-data-from-wsgi
    post_env = environ.copy()
    post_env["QUERY_STRING"] = ""
    return cgi.FieldStorage(
        fp=environ["wsgi.input"],
        environ=post_env,
        keep_blank_values=True
        )


def get_POST_fieldvalues(environ):
    fieldstore = get_POST_FieldStorage(environ)
    return dict((key, fieldstore.getvalue(key)) for key in fieldstore.keys())


PYTHON_WIDTH = 80

PYTHON_TOP = """
<hr>
<table><tr><td>
<pre style="font-family: monospace; font-size: small;">\
%(blank_line)s
"""

PYTHON_FORM = """\
<a id="input"/>\
<form method="post" action="">\
<textarea name="input_text" cols=%(width)s
    style="font-family: monospace; font-size: small;">
%(python_text)s</textarea>
<input type="submit" value="run" />\
</form>\
"""

PYTHON_COMPLETED = """\
<div style="background-color:%(color)s;">%(text)s</div>
"""

PYTHON_BOTTOM = """\
</pre>
</td></tr></table>
<hr>
"""

def simple_wrap(text, width, strip=False):
    results = []
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        while len(line) > width:
            results.append(line[:width])
            line = line[width:]
        results.append(line)
    while results and strip and results[0].strip() == "":
        results = results[1:]
    while results and strip and results[-1].strip() == "":
        results = results[:-1]
    return '\n'.join(results)


PYTHON_GLOBALS = {}  # exec code in PYTHON_GLOBALS
COMPLETED_ABOVE = []
COMPLETED_BELOW = []

def render_transaction(transaction, width):
    input, response, trace = transaction
    chunks = []
    for text, color, strip in [
            (input, "#e4e4e4", True),
            (response, "white", False),
            (trace, "#FFe4e4", False),
            ]:
        if text != None:
            text = simple_wrap(text, width, strip)
            chunks.append(fill_template(PYTHON_COMPLETED, locals()))
    return "".join(chunks)


def render_form(python_text, width):
    return fill_template(PYTHON_FORM, locals())


def interpret(code_text):
    saved_stdout = sys.stdout
    saved_stderr = sys.stderr
    output = StringIO.StringIO()
    trace = None
    try:
        sys.stdout = output
        sys.stderr = output
        
        tree = ast.parse(code_text, "<your input>")
        code1 = code2 = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_line = ast.Interactive(tree.body[-1:])
            tree.body = tree.body[:-1]
            code2 = compile(last_line, "<your input", "single")
        if tree.body:
            code1 = compile(tree, "<your input>", "exec")

        if code1:
            exec code1 in PYTHON_GLOBALS
        if code2:
            exec code2 in PYTHON_GLOBALS
    except Exception:
        trace = traceback.format_exc()
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
    return output.getvalue(), trace


PYTHON_TEXT = """print "Hello, World, I'm Python!" """

@route("/python/")
def do_python(environ, start_response):
    global PYTHON_TEXT
    
    chunks = html_header(environ, "Python Interpreter")
    raw_dict = {"blank_line": "&nbsp;" * PYTHON_WIDTH}
    chunks.append(fill_template(PYTHON_TOP, {}, raw_dict))

    if environ["REQUEST_METHOD"] == "POST":
        # Modify data before rendering.
        values = get_POST_fieldvalues(environ)
        input = values["input_text"]
        response, trace = interpret(input)
        COMPLETED_ABOVE.append( (input, response, trace) )
        if trace:
            PYTHON_TEXT = input
        else:
            PYTHON_TEXT = ""

    for transaction in COMPLETED_ABOVE:
        chunks.append(render_transaction(transaction, PYTHON_WIDTH))

    chunks.append(render_form(PYTHON_TEXT, PYTHON_WIDTH))
                      
    for transaction in COMPLETED_BELOW:
        chunks.append(render_transaction(transaction, PYTHON_WIDTH))

    chunks.append(PYTHON_BOTTOM)
    chunks += html_trailer(environ)

    do_headers(start_response, "200 OK", "text/html")
    return [ "".join(chunks) ]


# REQUEST_METHOD: GET
# QUERY_STRING: 
# _: ./serve_file.py
# PATH_INFO: /foo
# HTTP_HOST: 127.0.0.1:8000
# wsgi.multithread: True
# wsgi.multiprocess: False

# HTTP_USER_AGENT: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/537.22 (KHTML, like Gecko) Chrome/25.0.1364.99 Safari/537.22


if __name__ == "__main__":
    allow_files(argv[1:])
    httpd = make_server('', 8000, app)
    print "serving on port 8000"

    # Serve until process is killed
    httpd.serve_forever()
