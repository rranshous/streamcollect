

def application(environ, start_response):
    print 'app ran: %s' % (environ)
    start_response("200 OK",[('Content-type','octet-stream/ogg')])
    environ.get('feed_from_udp')(8089)
    return ""
