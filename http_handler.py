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

        # update the environ to include our helper methods
        self.environ.update({
            'create_udp_collector':self.server.manager.create_udp_collector,
            'feed_from_udp':self.feed_from_udp
        })


    def feed_from_udp(self,port):
        """
        once the WSGI app finished continue sending data to the client
        from a udp collector
        """

        # get the collector
        self.collector = man.get_or_create_collector(port)

        # we want all the data the collector's got
        self.collector.on('receive',self.handle_collector_data)

    def handle_collector_data(self, data):
        """
        add the data to our write buffer
        """
        self.outbuff += data

    def handle_close(self):
        # call our rent which will close the connection
        Super(HTTPHandler,self).handle_close()

        self.clean_up()

    def clean_up(self):
        """
        unregisters from the consumer and closees the connection
        """

        # unregister ourself from collector
        self.collector.un('receive',self.push)

    def writable(self):
        # if we are on a collector but don't have anything to go
        # out than return false. This way the SCGIConnector won't
        # think we are done and close the socket
        if self.collector and not self.outbuff:
            return False
        return Super(HTTPHandler,self).writable()
