from async import SCGIConnection

class HTTPHandler(SCGIConnection):
    wsgi_multithread = False
    wsgi_multiprocess = True
    wsgi_run_once = True

    def __init__(self, server, socket, addr, application):
        # respect the rents
        Super(HTTPHandler,self).__init__(server, socket, add)

        # where will we get our data ?
        self.collector = None


    ## WSGI BaseHandler
    def add_cgi_vars(self):
        self.environ.update({
            'create_collector':self.handler.create_collector,
            'get_or_create_collector':self.handle.create_collector,
            'hook_into_udp':self.handler
        })

    def handle_read(self):
        # let our rent handle it
        Super(HTTPHandler,self).handle_read()

        # if we have run than lets see if we need to hook
        # into the UDP stream
        if self.state == SCGIConnection.REQ and self.upd_collector_port:
            if not self.collector:
                # grab our manager
                man = self.server.manager

                # get the collector
                self.collector = man.get_or_create_collector(self.udp_port)

                # we want all the data the collector's got
                self.collector.on('receive',self.handle_collector_data)

    def handle_collector_data(self, data):
        """
        add the data to our write buffer
        """
        self.outbuff += data

    def handle_close(self):
        """
        unregisters from the consumer and closees the connection
        """

        # unregister ourself from collector
        self.collector.un('receive',self.push)

        # call our rent which will close the connection
        Super(HTTPHandler,self).handle_close()
