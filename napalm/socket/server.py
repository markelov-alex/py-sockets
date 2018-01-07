import socket
import socketserver
import threading

import sys

try:
    from twisted.internet import reactor, protocol
    from twisted.internet.protocol import connectionDone, Protocol
    from twisted.protocols.basic import LineReceiver
except ImportError:
    print("WARN! There is no twisted module!")


class ServerConfig:

    COMMAND_END = b"\x00"
    # 1200 - the most optimal max message size to fit IP(?) frame when using TCP
    RECV_SIZE = 1200  # 1024  # 4096

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def __init__(self, host="", port=0):
        self._host = host
        self._port = port
        
        # Define subclasses
        self.protocol_class = None


# Twisted


class TwistedHandler(LineReceiver):
    delimiter = b"\x00"
    app_protocol = None

    def connectionMade(self):
        print("TW SERVER", self, "+(connectionMade)")
        server_config = self.factory.app.lobby_model
        # Config
        self.delimiter = server_config.COMMAND_END
        # Create app protocol
        peer_address = self.transport.getPeer()
        self.app_protocol = server_config.protocol_class(self.sendLine, self.transport.loseConnection,
                                                         self.factory.app, (peer_address.host, peer_address.port))
        # self.app_protocol.send_bytes_method = self.sendLine
        # self.app_protocol.close_connection_method = self.transport.loseConnection

    def lineReceived(self, line):
        # line = line.decode()
        # print("TW SERVER", self, " (lineReceived) line:", line)
        if line:
            self.app_protocol.process_commands((line,))
    #
    # def sendLine(self, line):
    #     print("TW SERVER", self, " (sendLine) line:", line)
    #     super().sendLine(line)

    def connectionLost(self, reason=connectionDone):
        print("TW SERVER", self, "-(connectionLost)", reason)
        self.app_protocol.dispose()
        self.app_protocol = None


class TwistedHandlerFactory(protocol.ServerFactory):
    protocol = TwistedHandler

    def __init__(self, app):
        self.app = app

        # def buildProtocol(self, addr):
        #     p = self.protocol()
        #     p.factory = self
        #     return p

class TwistedTCPServer:
    def __init__(self, app):
        print("##(TwistedTCPServer.init) Create Server (Twisted, TCP)", app)
        if not app:
            raise Exception("No app object given!")

        self.server_config = app.lobby_model
        self.factory = TwistedHandlerFactory(app)

    def start(self):
        reactor.listenTCP(self.server_config.port, self.factory)
        reactor.run()


# Threaded + non-blocking

class ProtocolFactory:
    """
    Created to allow server to restore current session after player's reconnection
    within timeout interval. The problem: do users always have their unique hosts (IP)
    (port is always unique, so we cannot use (host,port) to identify the player).

    Maybe we should refuse from pooling protocol objects and use Player object pooling
    by auth token...
    """

    # We cannot pool removed items because address as a key is weak and we don't have another key
    REMOVED_ITEM_POOLING_ENABLED = False
    DISPOSE_OLD_PROTOCOL_TIMEOUT_SEC = 100

    # static
    dummy_protocol = None
    #
    # @property
    # def connection_count(self):
    #     return len(self.protocol_list)

    def __init__(self, app, protocol_class):
        self.app = app
        self.protocol_class = protocol_class

        # self.protocol_list = []

        # ProtocolFactory.dummy_protocol = protocol_class()
        # Protocol.dummy_protocol = protocol_class()
        print("#(ProtocolManager.init) create dummy protocol instance dummy_protocol:", ProtocolFactory.dummy_protocol)

    def dispose(self):
        print("#(ProtocolManager.dispose)")
        # for protocol in self.protocol_list:
        #     protocol.dispose()

        # self.protocol_list = []

        self.app = None
        self.protocol_class = None

        # ProtocolFactory.dummy_protocol = None
        # Protocol.dummy_protocol = None

    def create(self, send_bytes_method, close_method, address):
        app_protocol = self.protocol_class(send_bytes_method, close_method, self.app, address)
        # app_protocol.send_bytes_method = request.sendall
        # app_protocol.close_connection_method = request.close
        print("#(ProtocolManager.create) create new app_protocol:", app_protocol, "address:", address)
        return app_protocol


# Threaded

class ThreadedTCPServer:
    protocol_factory = None

    def __init__(self, app):
        print("##(ThreadedTCPServer.init) Create Server (Threaded, TCP)", app)
        if not app:
            raise Exception("No app object given!")
        self.server_config = app.lobby_model

        ThreadedTCPHandler.server_config = self.server_config
        ThreadedTCPServer.protocol_factory = ProtocolFactory(app, self.server_config.protocol_class)

    def start(self):
        if not self.server_config:
            return

        # (Try for multiple servers launched from a single main.py)
        # class CustomThreadedTCPHandler(ThreadedTCPHandler):
        #     pass
        # CustomThreadedTCPHandler.server_config = self.server_config


        # Create and start server
        print("##(ThreadedTCPServer.start) Start Server (Threaded, TCP)",
              (self.server_config.host, self.server_config.port))
        server = socketserver.ThreadingTCPServer((self.server_config.host, self.server_config.port), ThreadedTCPHandler)

        try:
            server.serve_forever()
        except KeyboardInterrupt as error:
            print("##(ThreadedTCPServer.start) ^C KeyboardInterrupt", error)

        # Here we shutdowning server

        print("##(ThreadedTCPServer.start) Set abort=True for all threads")
        # Abort other threads
        ThreadedTCPHandler.abort = True

        print("##(ThreadedTCPServer.start) Server shutdown and close")
        server.shutdown()
        server.server_close()
        ThreadedTCPServer.protocol_factory.dispose()
        print("##(ThreadedTCPServer.start) Finish")
        print("##(ThreadedTCPServer.start) Press Enter to exit...")
        input()
        # Needed to save lobby state using atexit.register() in app
        sys.exit()


class ThreadedTCPHandler(socketserver.BaseRequestHandler):
    # static
    abort = False

    recv_buffer = b""
    # is_first = True

    server_config = None

    protocol = None

    def setup(self):
        print("##(MyTCPHandler.setup)")
        self.protocol = ThreadedTCPServer.protocol_factory.create(self.send_bytes, self.request.close, self.client_address)

    def handle(self):
        # print("##(MyTCPHandler.handle) is_first:", self.is_first, self.server_config.port)
        # if self.is_first:
        #     self.request.sendall(b"Hello to client from server!")
        #     self.is_first = False

        current_thread = threading.current_thread()
        while not ThreadedTCPHandler.abort:
            print("## (MyTCPHandler.handle) New cycle. thread: {} client_address: {} request: {}".format(
                current_thread.getName(), self.client_address, self.request))

            print("##  (MyTCPHandler.handle) << Reading from client...")

            # Read data
            is_data = True
            while is_data and self.server_config.COMMAND_END not in self.recv_buffer:
                # print("##  (MyTCPHandler.handle)(temp) before-recv_buffer:", self.recv_buffer,
                #       is_data, self.server_config.COMMAND_END not in self.recv_buffer)
                try:
                    data_bytes = self.request.recv(self.server_config.RECV_SIZE)
                    is_data = bool(data_bytes)
                    # print("##  (MyTCPHandler.handle)(temp) data:", data_bytes, is_data)
                    print("##  <<< RECEIVE:", data_bytes, "length:", len(data_bytes))
                    # data_str = data_bytes.decode("utf-8")
                    # self.recv_buffer += data_str
                    self.recv_buffer += data_bytes
                except socket.error as error:
                    print("##  (MyTCPHandler.handle) Client disconnected!", error)
                    return

            if not self.recv_buffer:
                print("##No commands received. Possibly client suddenly disconnected!")
                return

            # Parse to command list
            # (Note: without str() b'10||true||##\x01\x00' after split() -> '0x0010||true||##\x01\x00')
            commands_data_list = self.recv_buffer.split(self.server_config.COMMAND_END)
            # print("##temp", len(self.recv_buffer),len(commands_data_list),
            #   self.server_config.COMMAND_END in self.recv_buffer)
            last_item = commands_data_list.pop()
            if last_item:
                self.recv_buffer = last_item
            else:
                self.recv_buffer = b""
            # print("##  (MyTCPHandler.handle) count,commands_data_list:", len(commands_data_list), commands_data_list)

            # Process command list
            try:
                if self.protocol:
                    self.protocol.process_commands(commands_data_list)
            except socket.error as error:
                print("##  (MyTCPHandler.handle) Client disconnected!", error)
                return

            print("##  (MyTCPHandler.handle) All commands processed.")

    def send_bytes(self, data_bytes):
        self.request.sendall(data_bytes + self.server_config.COMMAND_END)

    def finish(self):
        print("##(MyTCPHandler.finish)")
        # ThreadedTCPServer.protocol_factory.remove(self.protocol)
        self.protocol.dispose()

        self.server_config = None
        self.protocol = None


# Non-blocking

class NonBlockingTCPServer:

    def __init__(self, app):
        if not app:
            raise Exception("No app object given!")
        self.server_config = app.lobby_model

        self.request_by_protocol = {}
        self.buffer_by_protocol = {}

        self.protocol_factory = ProtocolFactory(app, self.server_config.protocol_class)
        self.protocol_list = []
        self.abort = False

    def start(self):
        if not self.server_config:
            return

        self.abort = False

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print("##(NonBlockingTCPServer.start) Start Server (NonBlocking, TCP)")

        address = (self.server_config.host, self.server_config.port)
        max_conn_num = 10
        print("##(NonBlockingTCPServer.start) Bind socket: %s max_conn_num: %i" % (address, max_conn_num))
        sock.bind(address)
        sock.listen(max_conn_num)

        try:
            self.workflow(sock)
        except KeyboardInterrupt as error:
            print("##(NonBlockingTCPServer.start) ^C KeyboardInterrupt", error)

        # print("##(NonBlockingTCPServer.start) Close all %i connections" % (
        #         self.protocol_factory.connection_count))
        print("##(NonBlockingTCPServer.start) Close all connections")
        self.protocol_factory.dispose()
        for protocol in self.protocol_list:
            protocol.dispose()
        self.protocol_list.clear()

        print("##(NonBlockingTCPServer.start) Shutdown server")
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except socket.error as error:
            print("##(NonBlockingTCPServer.start) Error while shutdowning!", error)
        sock.close()

        print("##(NonBlockingTCPServer.start) FINISH")
        print("##(NonBlockingTCPServer.start) Press Enter to exit...")
        input()

    def process_disconnect(self, protocol, error):
        print("##(NonBlockingTCPServer.process_disconnect) Client disconnected!", error)
        # self.protocol_factory.remove(protocol)
        # print("##  (NonBlockingTCPServer.process_disconnect) Connections: %i" % (
        #     self.protocol_factory.connection_count))
        if protocol in self.request_by_protocol:
            del self.request_by_protocol[protocol]
        if protocol in self.buffer_by_protocol:
            del self.buffer_by_protocol[protocol]
        self.protocol_list.remove(protocol)
        protocol.dispose()

    def workflow(self, sock):
        while not self.abort:
            # Connect
            # print("##\nWaiting for client connection...")

            sock.setblocking(0)
            request = None
            try:
                request, address = sock.accept()
            except socket.error as error:
                # print(error)
                pass
            if request:
                def send_bytes(data_bytes):
                    request.sendall(data_bytes + self.server_config.COMMAND_END)

                # Create protocol
                protocol = self.protocol_factory.create(send_bytes, request.close, address)
                self.request_by_protocol[protocol] = request
                self.protocol_list.append(protocol)
                print("##(NonBlockingTCPServer.workflow) Client accepted:", request, address)
                # print("##  (NonBlockingTCPServer.workflow) Connections: %i" % (
                #     self.protocol_factory.connection_count))
                # # Send the first message
                # print("##Send hello")
                # request.send(b"Hello from server!")

            for protocol in self.protocol_list:
                # Client-server workflow
                request = self.request_by_protocol[protocol]
                # request = protocol.request
                if not request:
                    continue

                # Read data
                is_data = True

                recv_buffer = self.buffer_by_protocol.get(self, b"")

                while is_data:
                    try:
                        data_bytes = request.recv(self.server_config.RECV_SIZE)
                        is_data = bool(data_bytes)
                        # data_str = data_bytes.decode("utf-8")
                        # recv_buffer += data_str
                        recv_buffer += data_bytes
                        # print(is_data, "|", data_bytes, "|", data_str, "|", recv_buffer,
                        #       self.server_config.COMMAND_END not in recv_buffer)
                    except socket.error as error:
                        # (break) is_data = False
                        if error.errno != 10035:
                            self.process_disconnect(protocol, error)
                        # Process next connection for both disconnect and no recv data
                        break

                if not recv_buffer:
                    continue

                print("##(NonBlockingTCPServer.workflow) Connection:", request)

                # Parse to command list
                commands_data_list = recv_buffer.split(self.server_config.COMMAND_END)
                # print("##  count,commands_data_list:", len(commands_data_list), commands_data_list, recv_buffer)
                last_item = commands_data_list.pop()

                recv_buffer = last_item
                self.buffer_by_protocol[self] = recv_buffer

                print("##  (NonBlockingTCPServer.workflow) Command list:", len(commands_data_list), commands_data_list)

                # Process command list
                try:
                    if protocol:
                        protocol.process_commands(commands_data_list)
                except socket.error as error:
                    self.process_disconnect(protocol, error)
                    return

                if commands_data_list:
                    print("##  (NonBlockingTCPServer.workflow) All commands processed.")
