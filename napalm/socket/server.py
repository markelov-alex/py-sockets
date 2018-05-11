import errno
import logging as _logging
import socket
import socketserver
import threading
import time

from napalm import utils

# Log
logging = _logging.getLogger("SERVER")
# Temp
# utils.default_logging_setup()

try:
    from twisted.internet import reactor
    from twisted.internet.protocol import connectionDone, Protocol, ServerFactory
    from twisted.protocols.basic import LineReceiver
except ImportError:
    logging.warning("There is no Twisted module!")

"""
Conventions:
"raw" - means data with delimiters, not splitted yet.
"data" - str data.
"data_bytes" - bytes data.
Servers and clients operate only with bytes. Protocol converts bytes to str and wise versa.
"""


# Common

class Config:
    DELIMITER = b"\x00"
    # 1200 - the most optimal max message size to fit IP(?) frame when using TCP
    RECV_SIZE = 1200  # 1024  # 4096

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def __init__(self, host="", port=0, protocol_class=None):
        self._host = host
        self._port = port
        self.protocol_class = protocol_class


class ServerConfig(Config):
    logging = None
    pass


class ProtocolFactory:
    """
    Single point of creating protocols to be used by any server type.
    """

    def __init__(self, config, app=None):
        self.config = config
        self.app = app

        self.protocol_class = config.protocol_class
        self.logging = logging if self.protocol_class and self.protocol_class.is_server_protocol else\
            _logging.getLogger("CLIENT")

    def dispose(self):
        self.logging.debug("ProtocolFactory dispose")
        self.config = None
        self.app = None
        self.protocol_class = None
        self.logging = None

    def create(self, send_bytes_method, close_connection_method, address):
        if not self.protocol_class:
            return None
        protocol = self.protocol_class(send_bytes_method, close_connection_method, address, self.config, self.app)
        self.logging.debug("ProtocolFactory create new protocol: %s for address: %s", protocol, address)
        return protocol


class AbstractServer:
    def __init__(self, config, app=None):
        self.config = config
        self.protocol_factory = ProtocolFactory(config, app)
        logging.debug("Server created. %s", self)

    def dispose(self):
        logging.debug("Server disposing...")
        self.stop()

        if self.protocol_factory:
            self.protocol_factory.dispose()
            self.protocol_factory = None
        self.config = None
        logging.debug("Server disposed")

    def start(self):
        raise NotImplemented

    def stop(self):
        raise NotImplemented


# Twisted

# TODO try to rename all protocol to protocol (all depend on TwistedHandler)
class TwistedHandler(LineReceiver):
    delimiter = b"\x00"
    protocol = None

    def connectionMade(self):
        # Config
        self.delimiter = self.factory.config.DELIMITER
        # Create app protocol
        address = self.transport.getPeer()
        self.protocol = self.factory.protocol_factory.create(self.sendLine, self.transport.loseConnection,
                                                             (address.host, address.port))
        logging.debug("connectionMade for %s protocol: %s", address, self.protocol)

    def rawDataReceived(self, data):
        # Not used while in line_mode
        pass

    def lineReceived(self, line):
        # logging.debug("dataReceived for %s line: %s", self.protocol, line)
        if line:
            self.protocol.process_bytes_list((line,))

    # def sendLine(self, line):
    #     logging.debug("sendData for %s line: %s", self.protocol, line)
    #     super().sendLine(line)

    def connectionLost(self, reason=connectionDone):
        logging.debug("connectionLost for %s reason: %s", self.protocol, reason)
        self.protocol.dispose()
        self.protocol = None


class TwistedTCPServer(AbstractServer):
    factory = None
    port = None

    def __init__(self, config, app=None):
        super().__init__(config, app)

        self.factory = ServerFactory()
        self.factory.protocol = TwistedHandler
        # Custom references
        self.factory.config = config
        self.factory.protocol_factory = self.protocol_factory

        self.started = False
        self.__started_lock = threading.RLock()

    def dispose(self):
        super().dispose()
        if self.factory:
            self.factory.config = None
            self.factory.protocol = None
            self.factory.protocol_factory = None
            self.factory = None

    def start(self):
        self.__started_lock.acquire()
        if self.started:
            logging.warning("Server is already running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        logging.debug("Server starting... address: %s", (self.config.host, self.config.port))
        self.started = True
        self.__started_lock.release()
        self.port = reactor.listenTCP(self.config.port, self.factory)
        if not reactor.running:
            reactor.run()
        logging.debug("Server started")

    def stop(self):
        self.__started_lock.acquire()
        if not self.started:
            logging.warning("Server is not running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        logging.debug("Server stopping...")
        self.started = False
        self.__started_lock.release()
        if self.port:
            # deferred = self.port.stopListening()
            # if deferred:
            #     event = threading.Event()
            #     event.clear()
            #
            #     def event_set():
            #         print("Waiting finished")
            #         event.set()
            #     deferred.addCallback(event_set)
            #     print("Waiting while listening stopping...", deferred)
            #     event.wait()
            #     print("Listening stopped")
            self.port.loseConnection()
            try:
                self.port.connectionLost(None)
            except Exception as error:
                # Bug in Twisted: sometimes AttributeError ('Port' object has no attribute 'socket') occurs
                # print("ERROR", error)
                pass
            self.port = None
        # -reactor.stop()
        # reactor.crash()
        logging.debug("Server stopped")

        # print("Press Enter to exit...")
        # input()
        # # Needed to save lobby state using atexit.register() in app
        # sys.exit()


# Threaded

class ThreadedTCPHandler(socketserver.BaseRequestHandler):
    # static
    abort = False

    buffer_bytes = b""
    # is_first = True

    config = None
    protocol = None

    def setup(self):
        threading.current_thread().name += "-srv-handler"
        self.config = self.server.config
        self.protocol = self.server.protocol_factory.create(self.send_bytes, self.request.close,
                                                            self.client_address)
        logging.debug("connectionMade for %s protocol: %s", self.client_address, self.protocol)

    def finish(self):
        logging.debug("connectionLost for %s", self.protocol)
        self.protocol.dispose()
        self.protocol = None
        self.config = None

    def send_bytes(self, data_bytes):
        # logging.debug("sendData for %s line: %s", self.protocol, data_bytes)
        self.request.sendall(data_bytes + self.config.DELIMITER)

    def handle(self):
        while not self.server.abort:
            # Read
            is_data = True
            data_bytes = None
            while not self.server.abort and is_data and self.config.DELIMITER not in self.buffer_bytes:
                try:
                    data_bytes = self.request.recv(self.config.RECV_SIZE)
                    is_data = bool(data_bytes)
                    self.buffer_bytes += data_bytes
                except socket.error as error:
                    # Note: current buffer won't be processed, but it usually empty in such cases
                    logging.debug(" (connectionLost (abort) for %s reason: %s)", self.protocol, error)
                    return

            # Parse bytes
            # b"command1##command2##\x00command3##\x00" -> [b"command1##command2##", b"command3##", b""]
            # b"1||param||##5||param||##\x0010||param||##\x00" ->
            #  [b"1||param||##5||param||##", b"10||param||##", b""]
            if self.buffer_bytes:
                # print("TEMP SERVER config:", self.server and self.config)
                data_bytes_list = self.buffer_bytes.split(self.config.DELIMITER)
                self.buffer_bytes = data_bytes_list.pop()

                # Process
                try:
                    # (Try-except: because send method could be invoked during processing)
                    if self.protocol and data_bytes_list:
                        self.protocol.process_bytes_list(data_bytes_list)
                # (Don't use socket.error because it causes StopIteration, which would not be caught)
                # except socket.error as error:
                except Exception as error:
                    logging.debug(" (connectionLost for %s reason: %s)", self.protocol, error)
                    return

            if not data_bytes:
                if not self.server.abort:
                    reason = "(Empty data received: %s)" % data_bytes
                    logging.debug(" (connectionLost for %s reason: %s)", self.protocol, reason)
                return


class ThreadedTCPServer(AbstractServer):
    server = None

    def __init__(self, config, app=None):
        super().__init__(config, app)

        self.started = False
        self.__started_lock = threading.RLock()
        self.__shutdown_event = threading.Event()
        self.__shutdown_event.set()

    # def dispose(self):
    #     super().dispose()

    def start(self):
        if not self.config:
            logging.error("Server is not initialized")
            return
        self.__started_lock.acquire()
        if self.started:
            logging.warning("Server is already running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        # Create and start server
        address = (self.config.host, self.config.port)
        logging.debug("Server starting... address: %s", address)
        self.started = True
        self.__started_lock.release()
        self.server = socketserver.ThreadingTCPServer(address, ThreadedTCPHandler)
        self.server.protocol_factory = self.protocol_factory
        self.server.config = self.config
        self.server.abort = False
        logging.debug("Server started")

        self.__shutdown_event.clear()
        try:
            self.server.serve_forever()
        except KeyboardInterrupt as error:
            logging.info("^C KeyboardInterrupt", error)

        # Here we shutting down the server
        logging.debug("Server shutting down...")
        # (Abort other threads)
        self.server.abort = True
        self.server.server_close()
        self.server.protocol_factory = None
        self.server.config = None
        self.server = None
        logging.debug("Server shut down")
        self.__shutdown_event.set()

        # print("Press Enter to exit...")
        # input()
        # # Needed to save lobby state using atexit.register() in app
        # sys.exit()

    def stop(self):
        self.__started_lock.acquire()
        if not self.started:
            logging.warning("Server is not running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        # Preventing
        logging.debug("Server stopping... address: %s", (self.config.host, self.config.port))
        self.started = False
        self.__started_lock.release()
        t = time.time()
        self.server.shutdown()
        self.__shutdown_event.wait()
        logging.debug("Server stopped in %f sec (95%% of time is exiting from serve_forever())", time.time() - t)


# Non-blocking

class NonBlockingTCPServer(AbstractServer):
    _sock = None

    def __init__(self, config, app=None):
        super().__init__(config, app)

        # (Needed for walking through all connections on each tick and receiving available data)
        self._protocol_list = []
        self._request_by_protocol = {}
        self._buffer_by_protocol = {}

        self._abort = False
        self.started = False
        self.__started_lock = threading.RLock()
        self.__shutdown_event = threading.Event()
        self.__shutdown_event.set()

    def start(self):
        if not self.config:
            logging.warning("Server is not initialized")
            return
        address = (self.config.host, self.config.port)
        logging.debug("Server starting... address: %s", address)
        self.__started_lock.acquire()
        if self.started:
            logging.warning("Server is already running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        self.started = True
        self.__started_lock.release()

        # (If restarting)
        self._abort = False

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self._sock.bind(address)
        self._sock.listen()
        self._sock.setblocking(0)
        logging.debug("Server started")

        self.__shutdown_event.clear()
        try:
            self._workflow(self._sock)
        except KeyboardInterrupt as error:
            logging.debug("^C KeyboardInterrupt %s", error)

        logging.debug("Server shutting down...")
        # self._abort = True
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except socket.error as error:
            logging.error("Error while shutting down: %s", error)
        self._sock.close()
        self._sock = None

        for protocol in self._protocol_list:
            protocol.dispose()
        self._protocol_list.clear()
        self._request_by_protocol.clear()
        self._buffer_by_protocol.clear()
        logging.debug("Server shut down")
        # logging.debug("Server stopped")
        self.__shutdown_event.set()

        # (For standalone. Bad for tests)
        # print("Press Enter to exit...")
        # input()
        # # Needed to save lobby state using atexit.register() in app
        # sys.exit()

    def stop(self):
        logging.debug("Server stopping...")
        self.__started_lock.acquire()
        if not self.started:
            logging.warning("Server is not running. address: %s", (self.config.host, self.config.port))
            self.__started_lock.release()
            return

        # If was started, but yet is not stopping
        self.started = False
        self.__started_lock.release()
        self._abort = True
        self.__shutdown_event.wait()
        logging.debug("Server stopped")

    def _process_disconnect(self, protocol, error):
        logging.debug("connectionLost for %s reason: %s", protocol, error)
        protocol.dispose()
        self._protocol_list.remove(protocol)
        if protocol in self._request_by_protocol:
            del self._request_by_protocol[protocol]
        if protocol in self._buffer_by_protocol:
            del self._buffer_by_protocol[protocol]

    def _workflow(self, sock):
        while not self._abort:
            # print("SERVER. While...")
            # Connect
            request, address = None, None
            try:
                request, address = sock.accept()
            # socket.error (real error is [WinError 10035])
            except Exception as error:
                # print("accept error:", error)
                # There is no new connections - skip
                pass
            if request:
                # New connection
                def send_bytes(data_bytes):
                    # logging.debug("sendData for %s line: %s", self.protocol, data_bytes)
                    request.sendall(data_bytes + self.config.DELIMITER)

                # Create protocol
                protocol = self.protocol_factory.create(send_bytes, request.close, address)
                logging.debug("connectionMade for %s protocol: %s", address, protocol)
                self._protocol_list.append(protocol)
                self._request_by_protocol[protocol] = request

            # Walk through all connections looking for new data to receive
            i = 0
            for protocol in self._protocol_list:
                i += 1
                request = self._request_by_protocol[protocol]

                # Read
                buffer_bytes = self._buffer_by_protocol.get(self, b"")
                is_data = True
                data_bytes = None
                while is_data:
                    try:
                        data_bytes = request.recv(self.config.RECV_SIZE)
                        is_data = bool(data_bytes)
                        buffer_bytes += data_bytes
                        # print("SERVER. recv data_bytes:", data_bytes, "buffer_bytes:", buffer_bytes)
                    # socket.error
                    except Exception as error:
                        # (break) is_data = False
                        # print("SERVER. Error (recv)", error)
                        if not hasattr(error, "errno") or error.errno != errno.EWOULDBLOCK:
                            self._process_disconnect(protocol, error)
                        # Process next connection for both disconnect and no data received now
                        break
                    if not data_bytes:
                        self._process_disconnect(protocol, "(Empty data received: %s)" % data_bytes)

                if not buffer_bytes:
                    continue

                # Parse bytes
                data_bytes_list = buffer_bytes.split(self.config.DELIMITER)
                self._buffer_by_protocol[self] = data_bytes_list.pop()

                # Process
                try:
                    # (Try-except: because send method could be invoked during processing)
                    if protocol and data_bytes_list:
                        logging.debug("dataReceived for %s line: %s", protocol, buffer_bytes)
                        protocol.process_bytes_list(data_bytes_list)
                # socket.error
                except Exception as error:
                    self._process_disconnect(protocol, error)
                    break
