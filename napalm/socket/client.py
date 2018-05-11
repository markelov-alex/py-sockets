import logging as _logging
import socket
import threading
import time
from threading import Thread

from twisted.internet import reactor
# from twisted.internet.endpoints import TCP4ClientEndpoint
from twisted.internet.protocol import ClientFactory

from napalm import utils
from napalm.socket.server import Config, ProtocolFactory, TwistedHandler

# from napalm.socket.test.test_server_with_client import ClientProtocol
from napalm.utils import PrintLogging

# Log
# Temp
# utils.default_logging_setup()
# Log
logging = _logging.getLogger("CLIENT")
logging.level = _logging.DEBUG
# (Original logger skips some messages so while debugging we use our substitution -
# there is something with default_logging_setup() for stdout (stdout.writ() & flush() called properly))
# logging = PrintLogging("CLIENTtmp")


# Common

class ClientConfig(Config):
    logging = None
    pass


class AbstractClient:
    """
    As client can have only one protocol instance unlike server does,
    we can deal without any protocol at all by overriding data_received.
    Using:
        # With protocol
        class ClientProtocol(SimpleProtocol):
            def on_connect(self):
                self.send_raw(b"Hello")

            def process_bytes(self, data_bytes):
                if data_bytes == b"Hi!":
                    self.send_raw(b"How are you?")
                elif data_bytes == b"And you?":
                    self.send_raw(b"I'm OK.")
                    self.send_raw(b"Good bye!")

        config = ClientConfig("your.server.com", 41000, ClientProtocol)
        client = TCPClient(config)
        client.connect()

        # Without protocol
        class MyTCPClient(TCPClient):
            def on_connect(self):
                self.send_raw(b"Hello")

            def data_received(self, data_bytes_list):
                for data_bytes in data_bytes_list:
                    if data_bytes == b"Hi!":
                        self.send_raw(b"How are you?")
                    elif data_bytes == b"And you?":
                        self.send_raw(b"I'm OK.")
                        self.send_raw(b"Good bye!")

        config = ClientConfig("your.server.com", 41000)
        client = MyTCPClient(config)
        client.connect()
    """
    logging = _logging.getLogger("CLIENT")

    def __init__(self, config=None, app=None):
        self.config = config or ClientConfig()
        self.protocol_factory = ProtocolFactory(self.config, app)
        self.logging.debug("Client created.")

    def dispose(self):
        self.logging.debug("Client disposing... %s", self)
        self.close()

        if self.protocol_factory:
            self.protocol_factory.dispose()
            self.protocol_factory = None
        self.config = None
        self.logging.debug("Client disposed. %s", self)

    def on_connect(self):
        pass

    def on_reconnect(self):
        pass

    def on_close(self):
        pass

    def connect(self, address=None, max_tries=0, try_interval=5):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


# Twisted

# Rough version
class TwistedTCPClient(AbstractClient):
    factory = None
    connector = None

    def __init__(self, config, app=None):
        super().__init__(config, app)

        self.factory = ClientFactory()
        self.factory.config = config
        self.factory.protocol = TwistedHandler
        self.factory.protocol_factory = self.protocol_factory

    def dispose(self):
        super().dispose()
        if self.factory:
            self.factory.config = None
            # self.factory.protocol = None
            self.factory.protocol_factory = None
            self.factory = None

    def connect(self, address=None, max_tries=0, try_interval=5):
        host = address[0] if address else self.config.host
        port = address[1] if address else self.config.port

        # endpoint = TCP4ClientEndpoint(reactor, host, port)
        # endpoint.connect(self.factory)
        # or in old way
        self.connector = reactor.connectTCP(host, port, self.factory)

        if not reactor.running:
            reactor.run()

    def close(self):
        if self.connector:
            self.connector.disconnect()
            self.connector = None
        # -reactor.stop()
        if self.on_close:
            self.on_close()
        # -if self.factory and self.factory.protocol:
        #     # ?-self.factory.protocol.dispose()
        #     self.factory.protocol = None


# Blocking

class BlockingTCPClient(AbstractClient):
    conn = None
    protocol = None
    address = None
    abort = False
    # (Used to continue after reconnection without data loses)
    buffer = b""
    # (Contain only the last unsent message, because pre-last messages don't raise exception)
    # ?needed?
    sending_buffer = None

    def __init__(self, config=None, app=None):
        super().__init__(config, app)

        self.connecting = False
        self.connected = False
        self.__connect_lock = threading.RLock()
        self.__closed_event = threading.Event()
        self.__closed_event.set()

    # def dispose(self):
    #     super().dispose()

    def connect(self, server_address=None, max_tries=0, try_interval=5):
        """
        :param server_address: tuple of (host, port) if not set in config or change needed
        :param max_tries: if 0 then try forever
        :param try_interval: time interval before one more connect try
        :return:
        """
        self.__connect_lock.acquire()
        if self.connecting or self.connected:
            self.__connect_lock.release()
            return

        self.connecting = True
        # self.conn = socket.socket()
        self.__connect_lock.release()
        if not server_address:
            server_address = (self.config.host, self.config.port)

        self.abort = False
        self.__closed_event.clear()
        tries_count = 0
        connect_count = 0
        while not self.abort:
            # Connecting...
            self.connecting = True
            self.logging.info("%s to %s... %s",
                              "Connecting" if not connect_count else "Reconnecting", server_address,
                              "try: " + str(tries_count + 1) + " of " + str(max_tries) if tries_count else "")
            try:
                # if not self.conn:
                self.conn = socket.socket()
                self.conn.connect(server_address)
            # (socket.error)
            except Exception as error:
                self.logging.error("No server! %s", error)
                if tries_count >= max_tries > 0:
                    self.logging.info("Tried % of %. No more tries.", tries_count, max_tries)
                    return
                tries_count += 1

                self.logging.info("Wait for: %s sec", try_interval)
                time.sleep(try_interval)
                continue

            # Connected
            self.connected = True
            self.connecting = False
            self.address = self.conn.getsockname()
            self.logging.info("Connected to %s Client address: %s", server_address, self.address)
            if not self.protocol:
                self.protocol = self.protocol_factory.create(self.send_raw, self.close, self.address)

            connect_count += 1
            if connect_count == 1 and self.on_connect:
                # (Note: protocol.on_connect() called from protocol's constructor)
                print("CLIENT-on_connect")
                self.on_connect()
            elif connect_count > 1:
                print("CLIENT-on_reconnect")
                if self.protocol and hasattr(self.protocol, "on_reconnect") and self.protocol.on_reconnect:
                    self.protocol.on_reconnect()
                if self.on_reconnect:
                    self.on_reconnect()

            # Receive/Send...
            # print("CLIENT###abort:", self.abort, self.protocol, connect_count)
            self._workflow()
            # print(" CLIENT###abort:", self.abort, self.protocol)

            # Closed (disconnected or aborted)
            if self.conn:
                self.logging.debug("Closing... conn: %s abort: %s", self.conn, self.abort)
                try:
                    # print("  CLIENT. Closing... conn: %s", self.conn, threading.current_thread())
                    self.conn.shutdown(socket.SHUT_RDWR)
                    self.conn.close()
                except Exception as error:
                    self.logging.error("Error while closing connection. %s", error)
                if self.on_close:
                    self.on_close()
                    # check, if callback is not from this class - delete (?-)
                self.address = None
                # (Should be the last)
                self.conn = None

            self.connected = False
            print("    CLIENT###abort:", self.abort, self.protocol)
            self.logging.debug("Closed. conn: %s abort: %s", self.conn, self.abort)

            # Connection lost. Reconnect... (if not aborted)
            tries_count = 0

        # Dispose session (aborted or no more reconnects available)
        if self.protocol:
            self.protocol.dispose()
            self.protocol = None
        self.logging.debug("Session disposed. conn: %s abort: %s", self.conn, self.abort)
        self.__closed_event.set()

    def close(self):
        self.__connect_lock.acquire()
        # if not self.conn:
        if not self.connecting and not self.connected:
            self.__connect_lock.release()
            return

        self.abort = True
        self.logging.debug("CLOSE abort: %s", self.abort)
        # Wait until client is closed
        # (Could not be called from data_received() or protocol because they are called from
        # the same thread and this would block entire client workflow)
        # self.__closed_event.wait()
        # (Release only after self.conn=None, that is, after client is closed)
        self.__connect_lock.release()

    def _workflow(self):
        # -if self.sending_buffer:
        #     # Resend after previous connection
        #     sending_buffer = self.sending_buffer
        #     self.sending_buffer = None
        #     self.logging.debug("Resend: %s", sending_buffer)
        #     self.send_raw(sending_buffer)

        while not self.abort:
            # Receive
            while not self.abort and self.config.DELIMITER not in self.buffer:
                try:
                    data_bytes = self.conn.recv(self.config.RECV_SIZE)
                    if data_bytes:
                        self.buffer += data_bytes
                    else:
                        self.logging.error("Connection lost (empty bytes received)! abort: %s", self.abort)
                        return
                except socket.error as error:
                    self.logging.error("Connection lost (while receiving)! %s", error)
                    return

            data_bytes_list = self.buffer.split(self.config.DELIMITER)
            self.logging.debug("Received: %s", self.buffer)
            self.buffer = data_bytes_list.pop()

            try:
                self.data_received(data_bytes_list)
            except socket.error as error:
                self.logging.error("Connection lost (while data processing)! %s", error)
                return

    def data_received(self, data_bytes_list):
        # (Override and add logic here if you are not using protocol)
        if self.protocol:
            self.protocol.process_bytes_list(data_bytes_list)

    def send_raw(self, data_bytes):
        if not data_bytes:
            return

        # if self.sending_buffer:
        #     print("Send raw self.sending_buffer:", self.sending_buffer)
        #     data_bytes = self.sending_buffer + data_bytes
        #     self.sending_buffer = None
        # # logging.debug("Send to server: %s", data_bytes)
        try:
            if not data_bytes.endswith(self.config.DELIMITER):
                data_bytes += self.config.DELIMITER

            self.conn.send(data_bytes)
            # self.sending_buffer = None
        # socket.error (WinError and others can be raised)
        except Exception as error:
            # # Note! If few messages were sent when server is unavailable error occurs only for the last one,
            # # that is, only the last message will be put into sending_buffer and the rest will be lost.
            # # -if self.sending_buffer is None:
            # self.sending_buffer = data_bytes
            # print("Send raw ERROR self.sending_buffer:", self.sending_buffer, "data_bytes:", data_bytes)
            # # -self.conn.shutdown(socket.SHUT_RDWR)
            # # self.conn.close()
            # # else:
            # #     self.sending_buffer += data_bytes
            self.logging.error("Connection lost (while sending)! %s", error)
            # return
            raise


# Threaded

class ThreadedTCPClient(BlockingTCPClient, Thread):
    # All logic implemented in protocol, which class defined in config
    address = None
    max_tries = 0
    try_interval = 5

    def __init__(self, config=None, app=None):
        BlockingTCPClient.__init__(self, config, app)
        Thread.__init__(self)

    def run(self):
        self.connect(self.address, self.max_tries, self.try_interval)
