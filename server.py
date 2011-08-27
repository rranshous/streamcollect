from bigsignal import Eventable

## we listen on UDP ports for incoming data
# and than pipe that data out via HTTP streams
# we also handle registering new UDP ports to listen
#  to over HTTP


class Manager(Eventable):
    def __init__(self,http_port):
        # map of UDP collectors
        self.collectors = {}

        # the http server waiting for clients to stream to
        self.http_server = HTTPServer(http_port,self)

    def create_collector(self,port):
        collector = Collector(port)
        self.collectors[port] = collector
        return collector
