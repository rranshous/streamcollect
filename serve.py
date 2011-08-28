import asyncore, sys
from manager import Manager
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

## file which you run to startup the servers / collectors


if __name__ == '__main__':
    # get our args
    http_port, application_name = tuple(sys.argv[1:])

    # read in the application
    mod = __import__(application_name)
    application = mod.application

    # setup the manager
    manager = Manager(int(http_port),application)

    # start the asyncore loop
    log.info('Starting')
    asyncore.loop()
