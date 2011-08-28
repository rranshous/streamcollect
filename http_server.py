from async import SCGIServer, SCGIConnection
from http_handler import HTTPHandler

"""
we want to create an HTTP server which routes requests to a wsgi app
but provides some extra functions in the environment to tap into
other data streams
"""


class HTTPServer(SCGIServer):
    def __init__(self,*args,**kwargs):
        # associate our manager
        self.manager = kwargs.get('manager')
        del kwargs['manager']

        # respect ur rents
        SCGIServer.__init__(self,*args,**kwargs)


    def handle_accept(self):
        """asyncore interface"""
        try:
            ret = self.accept()
        except socket.error, err:
            # See http://bugs.python.org/issue6706
            if err.args[0] not in (errno.ECONNABORTED, errno.EAGAIN):
                raise
        else:
            if ret is not None:
                conn, addr = ret
                handler = SCGIConnection(self, conn, addr, **self.conf)

