import asyncore, asynchat
import os, socket, string, sys
import StringIO
import logging
from bigsignal import Eventable

# setup logging
logging.basicConfig(level=logging.DEBUG)
log = logging

READ_SIZE = 1024


class Collector(asyncore.dispatcher,Eventable):

    def __init__(self,port):
        asyncore.dispatcher.__init__(self)
        Eventable.__init__(self)

        # open a udp socket
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)

        # listen on defined port
        self.bind(('', port))

    def handle_accept(self):
        # setup a transporter to collect the data we receive
        log.debug('Collector: Accepting connection')
        conn, addr = self.accept()
        log.info('Collector [%s]: Handling accept' % addr)
        Transporter(self, conn, addr)

    def close(self):
        # let everyone know we're closing and than close
        self.fire('close')
        self.close()

    def handle_write(self, data):
        """
        fire's receive event with data attached
        """

        # fire off our data
        self.fire('receive',data)
