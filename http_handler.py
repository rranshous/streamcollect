from async import SCGIConnection
import logging
import mimetools
import StringIO

log = logging.getLogger(__name__)

HTTP_TERMINATOR = "\r\n\r\n"

class HTTPHandler(SCGIConnection):
    wsgi_multithread = False
    wsgi_multiprocess = True
    wsgi_run_once = True

    blocksize = 1

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

        log.info('HTTPHandler: Initializing')

    def feed_from_udp(self,port):
        """
        once the WSGI app finished continue sending data to the client
        from a udp collector
        """

        log.info("HTTPHandler: Hooking into UDP stream %s" % port)

        # get the collector
        self.collector = self.server.manager.get_or_create_collector(port)

        # we want all the data the collector's got
        self.collector.on('receive',self.handle_collector_data)

    def handle_collector_data(self, data):
        """
        add the data to our write buffer
        """
        log.debug('HTTPHandler: handling collector data: %s' % len(data))
        if self.outheaders: # wait for headers
            self.outbuff += data
            log.debug('HTTPHandler: outbuff size: %s' % len(self.outbuff))
        else:
            log.debug("HTTPHandler: headers not out")

    def handle_close(self):
        # call our rent which will close the connection
        SCGIConnection.handle_close(self)
        log.info("HTTPHandler: Closing")

        self.clean_up()

    def clean_up(self):
        """
        unregisters from the consumer and closees the connection
        """

        # unregister ourself from collector
        if self.collector:
            self.collector.un('receive',self.handle_collector_data)

    def writable(self):
        # if we are on a collector but don't have anything to go
        # out than return false. This way the SCGIConnector won't
        # think we are done and close the socket

        #return SCGIConnection.writable(self)

        writable = SCGIConnection.writable(self)
        log.debug('SCGIconn writable: %s' % writable)

        # we've got some data, we're good to go
        if writable and self.outbuff:
            log.debug('outbuff, writable')
            return True

        # we haven't sent the headers yet, but we can
        if writable and self.outheaders != True:
            log.debug('outheaders, writable')
            return True

        if writable and self.wsgihandler and self.outheaders != True:
            log.debug('wsgihandler, writable')
            return True

        return False

    def handle_read(self):
        """C{asyncore} interface"""

        log.debug('HTTPHandler: handling read')

        # if we haven't gotten all the header's data yet
        if self.state == SCGIConnection.NEW:
            log.debug('HTTPHandler: NEW')
            # we are going to read until we get to the terminator.
            # when we get to the terminator we know we've read the entire header
            back_buff = ''

            # if we've received to much shut down
            if len(self.inbuff) > self.maxrequestsize:
                log.warning('HTTPHandler: Inbuff too big')
                self.close()
                return

            # get a character
            data = self.recv(1)

            # if we didn't get any data we're done for now
            if data is None:
                log.debug('HTTPHandler: no data')
                return

            # we got data, add it to our in buffer
            self.inbuff += data

            # see if we've hit the terminator
            if self.inbuff.endswith(HTTP_TERMINATOR):

                log.debug('HTTPHandler: Found terminator')

                # lose the terminator
                self.inbuff = self.inbuff[:-4]

                # update our state to know we just got the headers
                self.state = SCGIConnection.HEADER


        # the inbuff contains the headers
        if self.state == SCGIConnection.HEADER:
            log.debug("HTTPHandler: HEADER")

            # get the status line
            status = self.inbuff[:self.inbuff.find('\r\n')]
            self.inbuff = self.inbuff[len(status):]

            # parse the status line for the path_info, script_name, request_method
            method, path, prot = status.split()

            # parse the headers
            fp = StringIO.StringIO(self.inbuff)
            self.inbuff = ""
            request_info = mimetools.Message(fp)
            headers = request_info.dict

            # update the environ w/ the things from the status
            self.environ.update({
                'SCRIPT_NAME': '/',
                'REQUEST_METHOD': method.upper(),
                'PATH_INFO': path.split('/')[-1].split('?')[0],
                'SERVER_PROTOCOL': prot.upper(),
                'QUERY_STRING': path.split('?')[-1] if '?' in path else ''
            })

            # add the headers to the environ
            for k,v in headers.iteritems():
                self.environ[k.upper()] = v

            log.debug('HTTPHandler: headers: \n%s' % headers)

            # tell kick the rest of the processing to the body handler
            self.state = SCGIConnection.BODY

        # the rest of the data is body data
        if self.state == SCGIConnection.BODY:
            log.debug("HTTPHandler: BODY")

            # read data off the line
            if not data:
                log.debug('HTTPHandler: reading data')
                data = self.recv(self.blocksize)
                self.inbuff += data

            # the request could have body data or it could not
            # in the case that it has a content len we are going
            # to keep collecting until we hit that
            content_len = int(self.environ.get("CONTENT_LENGTH",0))

            if not content_len or len(self.inbuff) >= content_len:
                log.debug('HTTPHandler: Have all body data')

                self.body.write(self.inbuff)
                self.body.seek(0)
                self.inbuff = ""
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
                log.debug('HTTPHandler: collecting body data')


    def handle_write(self):
        """C{asyncore} interface"""
        assert self.state >= SCGIConnection.REQ
        if len(self.outbuff) < self.blocksize:
            print 'got WSGI data'
            self._try_send_headers()
            for data in self.wsgihandler:
                assert isinstance(data, str)
                if data:
                    self.outbuff += data
                    break
            # don't want to close on the colector
            if not self.collector and len(self.outbuff) == 0:
                if hasattr(self.wsgihandler, "close"):
                    self.wsgihandler.close()
                print 'closing'
                self.close()
                return
        try:
            print 'sending'
            sentbytes = self.send(self.outbuff[:self.blocksize])
        except socket.error:
            if hasattr(self.wsgihandler, "close"):
                self.wsgihandler.close()
            self.close()
            return
        self.outbuff = self.outbuff[sentbytes:]
