import asyncore, asynchat
import os, socket, string, sys
import StringIO
import logging

# setup logging
logging.basicConfig(level=logging.DEBUG)
log = logging

READ_SIZE = 1024

class Transporter(asynchat.async_chat):
    def __init__(self, collector, socket, addr):
        log.debug('Transporter [%s]: Initializing' % addr)
        asynchat.async_chat.__init__(self, socket)

        self.socket = socket
        self.collector = collector
        self.addr = addr

    def collect_incoming_data(self,data):
        log.debug('Transporter [%s]: Collecting data: %s' % (self.addr,
                                                             len(data)))
        # need to subclass this method
        self.handle_data(data)

    def handle_close(self):
        self.close()

class Collector(asyncore.dispatcher):

    def __init__(self,port):
        asyncore.dispatcher.__init__(self)

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

