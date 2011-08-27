



class SuperHandler(wsgiref.handler.BaseHandler):
    wsgi_multithread = False
    wsgi_multiprocess = True
    wsgi_run_once = True

    def __init__(self, application, server):
        Super(SuperHandler,self).__init__(application)
        self.server = server

    def add_cgi_vars(self):
        self.environ.update({
            'create_collector':self.server.manager.create_collector,
            'get_or_create_collector':self.server.manager.create_collector,
            'get_data_generator':self.server.manager.get_collector_generator
        })



class HTTPHandler(asynchat.async_chat):

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


    def collect_incoming_data(self, data):
        log.debug('Consumer: collecting incoming data')
        self.data = self.data + data
        if len(self.data) > 16384:
            # limit the header size to prevent attacks
            self.handle_close()

    def found_terminator(self):
        """
        Waits for header and than registers with consumer
        """
        if not self.header:
            # parse http header
            fp = StringIO.StringIO(self.data)
            request = string.split(fp.readline(), None, 2)

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


