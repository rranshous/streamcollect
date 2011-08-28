from async import SCGIConnection
import logging
import mimetools
log = logging.getLogger(__name__)

class HTTPHandler(SCGIConnection):
    wsgi_multithread = False
    wsgi_multiprocess = True
    wsgi_run_once = True

    def __init__(self,*args,**kwargs):
        # respect the rents
        SCGIConnection.__init__(self,*args,**kwargs)

        # where will we get our data ?
        self.collector = None

        # update the environ to include our helper methods
        self.environ.update({
            'create_udp_collector':self.server.manager.create_collector,
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
        SCGIConnection.handle_close(self)

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
        writable = False
        if self.collector and not self.outbuff:
            log.debug('collector but no outbuff')
            writable = False
        writable = SCGIConnection.writable(self)
        log.debug('checking writable: %s' % writable)
        return writable


    def handle_read(self):
        """C{asyncore} interface"""

        # if we haven't gotten all the header's data yet
        if self.state == SCGIConnection.NEW:
            # we are going to read until we get to the terminator.
            # when we get to the terminator we know we've read the entire header
            back_buff = ''
            while True:
                # if we've received to much shut down
                if len(self.inbuff) > self.maxrequestsize:
                    self.close()
                    return

                # get a character
                c = self.recv(1)

                # if we didn't get any data we're done for now
                if c is None:
                    break

                # we got data, add it to our in buffer
                self.inbuff += c

                # see if we've hit the terminator
                if self.inbuff.endswith(HTTP_TERMINATOR):

                    # lose the terminator
                    self.inbuff = self.inbuff[:-4]

                    # update our state to know we just got the headers
                    self.state = SCGIConnection.HEADER

        # the inbuff contains the headers
        if self.state == SCGIConnection.HEADER:

            # parse the headers
            fp = StringIO.StringIO(self.inbuff)
            self.inbuff = ""
            header = mimetools.Message(fp)

            # add the headers to the environ
            for k,v in headers.iteritems():
                self.environ[k] = v

            if not self.environ.get("CONTENT_LENGTH", "bad").isdigit():
                self.close()
                return

            self.reqlen = int(self.environ["CONTENT_LENGTH"])
            if self.reqlen > self.maxpostsize:
                self.close()
                return

            # tell kick the rest of the processing to the body handler
            self.state = SCGIConnection.BODY

        # the rest of the data is body data
        if self.state == SCGIConnection.BODY:
            # read data off the line
            data = self.recv(self.blocksize)
            self.inbuff += data

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

