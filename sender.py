
import asyncore, asynchat
import os, socket, string, sys
import StringIO
import logging
from bigsignal import Eventable


class HTTPSender(asynchat.async_chat,Eventable):
    """
    receives data from collector, sends again
    """

    def __init__(self, server, socket, addr):
        # respect the rents
        asynchat.async_chat.__init__(Self,socket)
        Eventable.__init__(self)

        # keep our datas
        self.server = server
        self.socket = socket
        self.addr = addr
        self.collector = None

        self.set_terminator("\r\n\r\n")
        self.header = None
        self.data = ""


    def handle_consumer_data(self,data):
        """
        the consumer we've registered with has new data for us
        """

        # push the data out
        self.push(data)

    def collect_incoming_data(self, data):
        log.debug('Consumer: collecting incoming data')
        self.data = self.data + data
        if len(self.data) > 16384:
            # limit the header size to prevent attacks
            self.handle_close()

    def get_port_from_path(self, path):
        """
        given a path returns the consumer
        """

        # strip the leading slash if it's there
        if path.startswith('/'):
            path = path[1:]

        return int(path)

    def found_terminator(self):
        """
        Waits for header and than registers with consumer
        """
        if not self.header:
            # parse http header
            fp = StringIO.StringIO(self.data)
            request = string.split(fp.readline(), None, 2)
            if len(request) != 3:
                # badly formed request; just shut down
                self.shutdown = 1
            else:
                # parse message header
                self.header = mimetools.Message(fp)

                # find our consumer from the path
                port = self.get_port_from_path(path)
                self.collector = self.server.manager.collectors.get(port)

                # if we didn't get a consumer it's a request
                # than we ask the manager to create one
                if not self.collector:
                    collector = self.server.manager.create_collector(port)
                    self.collector = collector

                # register w/ our collector waiting for data
                self.collector.on('receive',self.handle_consumer_data)

                # send back our headers
                self.set_terminator("\r\n")
                self.pushstatus(200, "OK")
                self.push('Content-type: application/octet-stream')
                self.push("\r\n\r\n")

            self.data = ""
        else:
            pass # we don't care what else they send

    def pushstatus(self, status, explanation="OK"):
        self.push("HTTP/1.0 %d %s\r\n" % (status, explanation))

    def handle_close(self):
        """
        unregisters from the consumer and closees the connection
        """

        # unregister ourself from collector
        self.collector.un('receive',self.handle_consumer_data)

        # close our connection
        self.close()


class HTTPServer(asyncore.dispatcher):

    def __init__(self, port, manager):
        # straitup listen for connections
        asyncore.dispatcher.__init__(self)

        self.manager = manager
        self.port = port
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.bind(("", port))
        self.listen(5)

    def handle_accept(self):
        log.info('Server: Handling accept')

        # accept the connection
        conn, addr = self.accept()

        # setup the sender
        sender = HTTPSender(self, conn, addr, consumer)

    def get_collector(self, port):
        return self.manager.collectors.get(port,None)

