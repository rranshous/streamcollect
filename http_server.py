import asyncore, asynchat
import os, socket, string, sys
import StringIO
import logging
from bigsignal import Eventable


"""
we want to create an HTTP server which routes requests to a wsgi app
but provides some extra functions in the environment to tap into
other data streams
"""


class HTTPServer(asyncore.dispatcher):

    def __init__(self, port, application):
        # straitup listen for connections
        asyncore.dispatcher.__init__(self)

        self.application = application
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(("", port))
        self.listen(5)

    def handle_accept(self):
        log.info('Server: Handling accept')

        # accept the connection
        conn, addr = self.accept()

        # send on to the handler
        HTTPHandler(self, conn, addr, self.application)
