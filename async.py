__all__ = []

import asyncore
import socket
import sys
# Cannot use io module as it is broken in 2.6.
# Writing a str to a io.StringIO results in an exception.
try:
    import cStringIO as io
except ImportError:
    import StringIO as io
import errno

class SCGIConnection(asyncore.dispatcher):
    """SCGI connection class used by L{SCGIServer}."""
    # connection states
    NEW    = 0*4 | 1 # connection established, waiting for request
    HEADER = 1*4 | 1 # the request length was received, waiting for the rest
    BODY   = 2*4 | 1 # the request header was received, waiting for the body
    REQ    = 3*4 | 2 # request received, sending response
    def __init__(self, server, connection, addr, maxrequestsize=65536,
                 maxpostsize=8<<20, blocksize=4096, config={}):
        asyncore.dispatcher.__init__(self, connection)

        self.server = server # WSGISCGIServer instance
        self.addr = addr # scgi client address
        self.maxrequestsize = maxrequestsize
        self.maxpostsize = maxpostsize
        self.blocksize = blocksize
        self.state = SCGIConnection.NEW # internal state
        self.environ = config.copy() # environment passed to wsgi app
        self.reqlen = -1 # request length used in two different meanings
        self.inbuff = "" # input buffer
        self.outbuff = "" # output buffer
        self.wsgihandler = None # wsgi application iterator
        self.outheaders = () # headers to be sent
                             # () -> unset, (..,..) -> set, True -> sent
        self.body = io.StringIO() # request body

    def _wsgi_headers(self):
        return {"wsgi.version": (1, 0),
                "wsgi.input": self.body,
                "wsgi.errors": self.server.error,
                "wsgi.url_scheme": "http",
                "wsgi.multithread": False,
                "wsgi.multiprocess": False,
                "wsgi.run_once": False}

    def _try_send_headers(self):
        if self.outheaders != True:
            assert not self.outbuff
            status, headers = self.outheaders
            headdata = "".join(map("%s: %s\r\n".__mod__, headers))
            self.outbuff = "Status: %s\r\n%s\r\n" % (status, headdata)
            self.outheaders = True

    def _wsgi_write(self, data):
        assert self.state >= SCGIConnection.REQ
        assert isinstance(data, str)
        if data:
            self._try_send_headers()
            self.outbuff += data

    def readable(self):
        """C{asyncore} interface"""
        return self.state & 1 == 1

    def writable(self):
        """C{asyncore} interface"""
        return self.state & 2 == 2

    def handle_read(self):
        """C{asyncore} interface"""
        data = self.recv(self.blocksize)
        self.inbuff += data
        if self.state == SCGIConnection.NEW:
            if ':' in self.inbuff:
                reqlen, self.inbuff = self.inbuff.split(':', 1)
                if not reqlen.isdigit():
                    self.close()
                    return # invalid request format
                reqlen = int(reqlen)
                if reqlen > self.maxrequestsize:
                    self.close()
                    return # request too long
                self.reqlen = reqlen
                self.state = SCGIConnection.HEADER
            elif len(self.inbuff) > self.maxrequestsize:
                self.close()
                return # request too long

        if self.state == SCGIConnection.HEADER:
            buff = self.inbuff[:self.reqlen]
            remainder = self.inbuff[self.reqlen:]

            while buff.count('\0') >= 2:
                key, value, buff = buff.split('\0', 2)
                self.environ[key] = value
                self.reqlen -= len(key) + len(value) + 2

            self.inbuff = buff + remainder

            if self.reqlen == 0:
                if self.inbuff.startswith(','):
                    self.inbuff = self.inbuff[1:]
                    if not self.environ.get("CONTENT_LENGTH", "bad").isdigit():
                        self.close()
                        return
                    self.reqlen = int(self.environ["CONTENT_LENGTH"])
                    if self.reqlen > self.maxpostsize:
                        self.close()
                        return
                    self.state = SCGIConnection.BODY
                else:
                    self.close()
                    return # protocol violation

        if self.state == SCGIConnection.BODY:
            if len(self.inbuff) >= self.reqlen:
                self.body.write(self.inbuff[:self.reqlen])
                self.body.seek(0)
                self.inbuff = ""
                self.reqlen = 0
                self.environ.update(self._wsgi_headers())
                if self.environ.get("HTTPS", "no").lower() in ('yes', 'y', '1'):
                    self.environ["wsgi.url_scheme"] = "https"
                if "HTTP_CONTENT_TYPE" in self.environ:
                    self.environ["CONTENT_TYPE"] = \
                                self.environ.pop("HTTP_CONTENT_TYPE")
                if "HTTP_CONTENT_LENGTH" in self.environ:
                    del self.environ["HTTP_CONTENT_LENGTH"] # TODO: better way?
                self.wsgihandler = iter(self.server.wsgiapp(
                                self.environ, self.start_response))
                self.state = SCGIConnection.REQ
            else:
                self.body.write(self.inbuff)
                self.reqlen -= len(self.inbuff)
                self.inbuff = ""

    def start_response(self, status, headers, exc_info=None):
        assert isinstance(status, str)
        assert isinstance(headers, list)
        if exc_info:
            if self.outheaders == True:
                try:
                    raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    exc_info = None
        assert self.outheaders != True # unsent
        self.outheaders = (status, headers)
        return self._wsgi_write

    def handle_write(self):
        """C{asyncore} interface"""
        assert self.state >= SCGIConnection.REQ
        if len(self.outbuff) < self.blocksize:
            self._try_send_headers()
            for data in self.wsgihandler:
                assert isinstance(data, str)
                if data:
                    self.outbuff += data
                    break
            print 'got WSGI data'
            if len(self.outbuff) == 0:
                if hasattr(self.wsgihandler, "close"):
                    self.wsgihandler.close()
                print 'closing'
                self.close()
                return
        try:
            print 'sending'
            sentbytes = self.send(self.outbuff[:self.blocksize])
        except socket.error:
            if hasattr(self.wsgihandler, "close"):
                self.wsgihandler.close()
            self.close()
            return
        self.outbuff = self.outbuff[sentbytes:]

    def handle_close(self):
        """C{asyncore} interface"""
        self.close()

__all__.append("SCGIServer")
class SCGIServer(asyncore.dispatcher):
    """SCGI Server for WSGI applications. It does not use multiple processes or
    multiple threads."""
    def __init__(self, wsgiapp, port, interface="localhost", error=sys.stderr,
                 maxrequestsize=None, maxpostsize=None, blocksize=None,
                 config={}):
        """
        @param wsgiapp: is the wsgi application to be run.
        @type port: int
        @param port: is an int representing the TCP port number to be used.
        @type interface: str
        @param interface: is a string specifying the network interface to bind
                which defaults to C{"localhost"} making the server inaccessible
                over network.
        @param error: is a file-like object being passed as C{wsgi.error} in the
                environ parameter defaulting to stderr.
        @type maxrequestsize: int
        @param maxrequestsize: limit the size of request blocks in scgi
                connections. Connections are dropped when this limit is hit.
        @type maxpostsize: int
        @param maxpostsize: limit the size of post bodies that may be processed
                by this instance. Connections are dropped when this limit is
                hit.
        @type blocksize: int
        @param blocksize: is amount of data to read or write from or to the
                network at once
        @type config: {}
        @param config: the environ dictionary is updated using these values for
                each request.
        """
        asyncore.dispatcher.__init__(self)

        self.wsgiapp = wsgiapp
        self.error = error
        self.conf = {}
        if maxrequestsize is not None:
            self.conf["maxrequestsize"] = maxrequestsize
        if maxpostsize is not None:
            self.conf["maxpostsize"] = maxpostsize
        if blocksize is not None:
            self.conf["blocksize"] = blocksize
        self.conf["config"] = config

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((interface, port))
        self.listen(5)

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
                SCGIConnection(self, conn, addr, **self.conf)

    def run(self):
        """Runs the server. It will not return and you can invoke
        C{asyncore.loop()} instead achieving the same effect."""
        asyncore.loop()

