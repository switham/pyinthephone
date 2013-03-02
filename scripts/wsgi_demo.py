#!/usr/bin/env python
"""
wsgi_demo.py--WSGI server with templating, a routing decorator, and some demos.
RUN FROM THE wsgi_demo directory: scripts/wsgi_demo.py [files...]
The wsgi_demo directory corresponds to /mnt/sdcard/sl4a on Android --
scripts run there but are read from    /mnt/sdcard/sl4a/scripts.

Arguments on the command line name files users are allowed to view & download.
(Paths are relative to the directory where wsgi_demo.py is run.)

This code is insecure!
    It displays your Unix environment variables.
    It shows Python exceptions on the 404 page.
    It's vulnerable to code-injection attacts (although I made some vain
    gestures).
    wsgi_self_serv.py makes this script display its own source code.
"""

from wsgiref.simple_server import make_server
import os
from sys import argv, exit
from mimetypes import guess_type


header_template = """<!DOCTYPE html>
<html>

<head>
<title>{{title}}</title>
</head>

<body>
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
 

def fill_template(template, subs_dict):
    """
    If dict contains, e.g., "A": "foo", then
    "{{A}}" in template will be replaced by "foo".
    Not at all smart about escaping, recursion and whatnot.
    """
    text = template
    for key, value in subs_dict.iteritems():
        # dict may contain junk non-text items:
        if isinstance(value, basestring):
            text = text.replace("{{" + key + "}}", value)
    return text
    

ROUTES = {}

def route(path):
    """
    path should either
       start with "/" and end with "/*" --wildcard match-- or
       start with "/" but not include "*" --exact match.
    Pattern of use:
       @route("/")
       @route("/index.html")
       def home_page(environ, start_response):
           # home_page() can look at environ["PATH_INFO"] to see path.
           ...
           return text
    Matches (e.g. /foo/* matches /foo/bar) are tried most-specific-first;
        "/foo" is different from "/foo/";
        "/foo/" is more specific than "/foo/*".
    """

    assert path.startswith("/")
    assert path.endswith("/*") or "*" not in path
    if path.endswith("/*"):
        assert "*" not in path[:-1]
    
    def route_setter(function):
        ROUTES[path] = function
        return function  # Unchanged.

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


def do_route(environ, start_response):
    """
    Route the request to the appropriate callable in the ROUTES table.
    Sets environ["wildcard_part"] = what matches the * in, e.g.  "/foo/*".
    """
    environ["wildcard_part"] = ""
    
    path = environ["PATH_INFO"]
    assert "*" not in path, "'*' in path."
    assert "//" not in path, "'//' in path."
    
    parts = environ["PATH_INFO"].split("/")
    assert ".." not in parts, "'..' is a no-no."
    assert parts and parts[0] == '', "path should start with /"

    if path in ROUTES:  # All exact matches are caught here.
        return ROUTES[path](environ, start_response)

    for n in range(len(parts) - 1, 0, -1):
        if parts[n] == "":  # foo/ should not match foo/* below.
            continue

        subpath = "/".join(parts[:n]) + "/"
        if path.startswith(subpath):
            wildpath = subpath + "*"
            if wildpath in ROUTES:
                environ["wildcard_part"] = "/".join(parts[n:])
                return ROUTES[wildpath](environ, start_response)

    return do_404(environ, start_response)


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
        chunks = do_route(environ, start_response)
        if environ["REQUEST_METHOD"] == "HEAD":
            # I am not going to try to return the correct Content-Length.
            return []

        return chunks
    except KeyboardInterrupt:
        exit(1)
        
    except Exception, e:
        return do_404(environ, start_response, complaint=repr(e))


@route("/")
@route("/index.html")
@route("/welcome.html")
def home_page(environ, start_response):
    do_headers(start_response, "200 OK", "text/plain")
    return ["Welcome to the script at\n" + os.path.abspath(__file__)]


@route("/favicon.ico")
def icon(environ, start_response):
    actual_file_path = "data/SL4A2.jpg"
    contents = file(actual_file_path).read()
    do_headers(start_response, "200 OK", just_guess_type(actual_file_path))
    return [contents]



@route("/environ")
@route("/environ/*")
def dump_environ(environ, start_response):
    chunks = ["os.getcwd(): " + os.getcwd() + "\n", "\n"]
    chunks += ["%s: %r\n" % (key, value)
                    for key, value in environ.iteritems()]
    do_headers(start_response, "200 OK", "text/plain")
    return [ "".join(chunks) ]


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

    chunks.append("<br>look <a href='http://www.digiblog.de/2011/04/android-and-the-download-file-headers/'>here</a>, too.\n")

    chunks += html_trailer(environ)

    do_headers(start_response, "200 OK", "text/html")
    return [ "".join(chunks) ]

    
@route("/static/*")
def do_static(environ, start_response):
    path = environ["wildcard_part"]
    assert not path.endswith("/"), "I won't list that directory."

    if path in ALLOWED_FILES:
        do_headers(start_response, "200 OK", just_guess_type(path))
        return [file(path).read()]
    else:
        return do_404(environ, start_response)


@route("/download/*")
def do_download(environ, start_response):
    path = environ["wildcard_part"]
    assert not path.endswith("/"), "I don't do that directory."

    if path in ALLOWED_FILES:
        download_path = '"' + path.replace("_", "") + '"'
        do_headers(start_response, "200 OK", None,
                  ("Content-Disposition",
                    "attachment; filename=%s" % download_path),
                  ("Content-Type", "application/octet-stream"),
            )
        return [file(path).read()]
    else:
        return do_404(environ, start_response)


textarea_body = """
Go ahead and edit the following:
<p>

<form method="post" action="">
<textarea name="comments" cols=80 style="font-family: monospace;">
{{textarea_text}}
</textarea><br>
<input type="submit" value="run" />
</form>

<p>

We hope you've enjoyed your experience; come again!
"""

n_monkeys = 0

@route("/textarea")
def textarea(environ, start_response):
    global n_monkeys
    chunks = html_header(environ, "The Monkey Textarea")

    n_monkeys += 1
    textarea_text = "Welcome to Monkey Textarea " + str(n_monkeys)
    chunks.append(fill_template(textarea_body, locals()))

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
