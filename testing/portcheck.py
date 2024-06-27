import time
import socket

class Test:
    def __init__(self):
        self.name = 'test'

    def try_until(self, f, seconds, errmsg):
        '''Try f periodically until seconds elapse'''
        start = time.monotonic_ns()
        while True:
            now = time.monotonic_ns()
            if (now - start > seconds * 1e9):
                print(errmsg)
                return
            if f():
                return
            time.sleep(0.1)

    def check_listen(self, port, ipv6=False):
        '''Check for a particular port being listened on'''
        def test():
            Connected = False
            rc = False
            print(f"Initial entry test for {port}")
            try:
                try:
                    Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) #Create a socket.
                except:
                    Connected = False

                Socket.connect(("127.0.0.1", port)) #Try connect the port. If port is not listening, throws ConnectionRefusedError.
                print(f"Connected to {port}")
                Connected = True
            except ConnectionRefusedError:
                print('Connection Refused')
                Connected = False
            finally:
                socketPort = Socket.getsockname()[1]
                if (Connected and port != socketPort): #If connected,
                    rc = True
                    Socket.close() #Close socket.
                    print(f"All good: {Connected} Port {port} Socket Port {socketPort}")
                else:
                    print(f"Connected {Connected} Port {port}")
                    rc = False
            return rc

        self.try_until(test, 2, f"Port {port} is not bound")

test = Test()

test.check_listen(992)
