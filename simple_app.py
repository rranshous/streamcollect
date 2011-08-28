

def application(environ, start_response):
    print 'app ran'
    start_response()
    return ""
