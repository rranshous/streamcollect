import asyncore, asynchat
import os, socket, string, sys
import StringIO
import logging
from bigsignal import Eventable

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

READ_SIZE = 1024


class UDPCollector(asyncore.dispatcher,Eventable):

    blocksize = 1024

    def __init__(self,port):
        asyncore.dispatcher.__init__(self)
        Eventable.__init__(self)

        # open a udp socket
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)

        # listen on defined port
        log.info('UDPCollector: binding to %s' % port)
        self.bind(('', port))
        self.port = port

    def handle_accept(self):
        # setup a transporter to collect the data we receive
        log.debug('Collector: Accepting connection')
        conn, addr = self.accept()
        log.info('Collector [%s]: Handling accept' % self.port)
        Transporter(self, conn, addr)

    def handle_close(self):
        # let everyone know we're closing and than close
        log.info("UDPCollector [%s]: closing" % self.port)
        self.fire('close')
        self.close()

    def writable(self):
        return False

    def handle_read(self):
        """
        fire's receive event with data attached
        """
        # fire off our data
        data = self.recv(self.blocksize)
        log.debug("UDPCollector [%s]: received %s" % (self.port,len(data)))
        self.fire('receive',data)



