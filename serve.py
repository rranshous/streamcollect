import asyncore
from manager import Manager

## file which you run to startup the servers / collectors


if __name__ == '__main__':
    # get our args
    http_port, application_name = tuple(sys.argv[1:])

    # read in the application
    __import__(application_name)
    application = globals().get(application_name).application

    # setup the manager
    manager = Manager(int(http_port),application)

    # start the asyncore loop
    asyncore.loop()
