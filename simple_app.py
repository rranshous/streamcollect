

def application(environ, start_response):
    print 'app ran'
    start_response("200 OK",[('Content-type','text/html')])
    return "test!"
