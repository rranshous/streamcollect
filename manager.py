from udp_collector import collector
from http_server import HTTPServer

## we listen on UDP ports for incoming data
# and than pipe that data out via HTTP streams
# we also handle registering new UDP ports to listen
#  to over HTTP


class Manager(object):
    def __init__(self,http_port,application):
        # map of UDP collectors
        self.collectors = {}

        # some base env variables for accessing our helpers
        base_env = {
            'create_collector': self.create_collector
        }

        # the http server waiting for clients to stream to
        self.http_server = HTTPServer(application, http_port, base_env)

    def get_or_create_collector(self,port):
        """
        if a collector exists for the port get it, if not
        create one and than return it
        """

        port = int(port)
        if port not in self.collectors:
            collector = self.create_collector(port)
        return self.collectors.get(port)

    def create_collector(self,port):
        """
        creates a collector
        """
        collector = UDPCollector(port)
        self.collectors[port] = collector
        return collector

