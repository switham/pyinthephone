#!/usr/bin/env python
""" wsgi_textarea.py -- Serve a form with a textarea. """

from wsgiref.simple_server import make_server
import os

page_template = """<!DOCTYPE html>
<html>

<head>
<title>wsgi_hello2</title>
</head>

<body>
Welcome from the script at<br>
{{script_path}} !
<p>

Go ahead and edit the following:
<p>

<form method="post" action="">
<textarea name="comments" cols=80 style="font-family: monospace;">
Welcome to the Monkey Textarea!
</textarea><br>
<input type="submit" value="run" />
</form>

<p>

We hope you've enjoyed your experience; come again!

</body>
</html>
"""


def fill_template(template, subs_dict):
    """
    If dict contains, e.g., "A": "foo", then
    "{{A}}" in template will be replaced by "foo".
    Not at all smart about escaping, recursion and whatnot.
    """
    text = template
    for key, value in subs_dict.iteritems():
        if isinstance(value, basestring):
            text = text.replace("{{" + key + "}}", value)
    return text
    

# Every WSGI application must have an application object - a callable
# object that accepts two arguments. For that purpose, we're going to
# use a function (note that you're not limited to a function, you can
# use a class for example). The first argument passed to the function
# is a dictionary containing CGI-style envrironment variables and the
# second variable is the callable object (see PEP 333).
def app(environ, start_response):
    status = '200 OK' # HTTP Status
    headers = [('Content-type', 'text/html')] # HTTP Headers
    start_response(status, headers)

    # The returned object is going to be printed
    
    script_path = os.path.abspath(__file__)
    return fill_template(page_template, locals())


if __name__ == "__main__":
    port_no = 8000
    httpd = make_server('', port_no, app)
    print "serving on port", port_no

    # Serve until process is killed
    httpd.serve_forever()
