

class HTTPHandler(asynchat.async_chat,wsgiref.handler.BaseHandler):
    wsgi_multithread = False
    wsgi_multiprocess = True
    wsgi_run_once = True

    def __init__(self, server, socket, addr, application):
        # respect the rents
        asynchat.async_chat.__init__(self,socket)
        wsgiref.handler.BaseHandler.__init__(self,application)

        # keep our datas
        self.server = server
        self.socket = socket
        self.addr = addr
        self.collector = None

        self.set_terminator("\r\n\r\n")
        self.header = None
        self.data = ""


    ## WSGI BaseHandler
    def add_cgi_vars(self):
        self.environ.update({
            'create_collector':self.handler.create_collector,
            'get_or_create_collector':self.handle.create_collector,
            'hook_into_udp':self.handler
        })


    def get_stdin(self):
        return None

    def _write(self,data):
        self.push(data)

    def _flush(self):
        pass


    ## async_chat methods
    def collect_incoming_data(self, data):
        # add the data to our buffer
        self.data += data

    def found_terminator(self):
        """
        Waits for header and than registers with consumer
        """
        if not self.header:
            # run the handler
            self.run(self.application)

            # if our flag says so, we want to hook into a collector
            if self.udp_port and not self.collector:
                man = self.server.manager
                self.collector = man.get_or_create_collector(self.udp_port)
                # we want all the data the collector's got
                self.collector.on('receive',self.push)

    def handle_close(self):
        """
        unregisters from the consumer and closees the connection
        """

        # unregister ourself from collector
        self.collector.un('receive',self.push)

        # close our connection
        self.close()
