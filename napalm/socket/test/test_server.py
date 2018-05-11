import logging
import random
import socket
import socketserver
from threading import Thread, Event, Barrier
from unittest import TestCase
from unittest.mock import Mock, MagicMock, call, patch

import time

import errno
from twisted.internet import reactor
from twisted.internet.protocol import ServerFactory

from napalm.core import SocketGameApplication
from napalm.socket.protocol import Protocol, SimpleProtocol, ServerProtocol
from napalm.socket.server import Config, ServerConfig, ProtocolFactory, AbstractServer, NonBlockingTCPServer
from napalm.socket.server import TwistedHandler, TwistedTCPServer, ThreadedTCPHandler, ThreadedTCPServer

# TODO TEST with protocol raises exception during processing

logging.basicConfig(level=logging.DEBUG)


class MySpecificException(Exception):
    pass


# Common

class TestConfig(TestCase):
    def setUp(self):
        self.config = Config("some host", 123, Protocol)

    def test_properties(self):
        self.assertEqual(self.config.host, "some host")
        self.assertEqual(self.config.port, 123)
        self.assertEqual(self.config.DELIMITER, b"\x00")
        self.assertLessEqual(self.config.RECV_SIZE, 1200)
        self.assertEqual(self.config.protocol_class, Protocol)

    def test_empty(self):
        self.config = Config()

        self.assertEqual(self.config.host, "")
        self.assertEqual(self.config.port, 0)
        self.assertIsNone(self.config.protocol_class)

    def test_server_config(self):
        self.assertTrue(issubclass(ServerConfig, Config))
        # No exception
        ServerConfig()


class TestProtocolFactory(TestCase):
    config = ServerConfig(protocol_class=ServerProtocol)
    app = SocketGameApplication(config)

    def setUp(self):
        super().setUp()
        self.protocol_factory = ProtocolFactory(self.config, self.app)

    def test_dispose(self):
        self.assertIsNotNone(self.protocol_factory.config)
        self.assertIsNotNone(self.protocol_factory.app)
        self.assertIsNotNone(self.protocol_factory.protocol_class)

        self.protocol_factory.dispose()

        self.assertIsNone(self.protocol_factory.config)
        self.assertIsNone(self.protocol_factory.app)
        self.assertIsNone(self.protocol_factory.protocol_class)

    def test_create(self):
        send_bytes_method, close_connection_method, address = Mock(), Mock(), Mock()
        self.protocol_factory.protocol_class = protocol_class = Mock()

        self.protocol_factory.create(send_bytes_method, close_connection_method, address)

        protocol_class.assert_called_once_with(send_bytes_method, close_connection_method, address, self.config,
                                               self.app)

    def test_create_real(self):
        send_bytes_method, close_connection_method, address = Mock(), Mock(), Mock()
        self.protocol_factory.protocol_class = Protocol

        protocol = self.protocol_factory.create(send_bytes_method, close_connection_method, address)

        self.assertIsInstance(protocol, Protocol)
        self.assertEqual(protocol.send_bytes_method, send_bytes_method)
        self.assertEqual(protocol.close_connection_method, close_connection_method)
        self.assertEqual(protocol.config, self.config)
        # self.assertEqual(protocol.app, self.app)
        self.assertEqual(protocol.address, address)


class TestAbstractServer(TestCase):
    config = ServerConfig("somehost", 12345, Protocol)
    app = SocketGameApplication(config)

    def setUp(self):
        super().setUp()
        self.server = AbstractServer(self.config, self.app)

    def test_init(self):
        self.assertEqual(self.server.config, self.config)
        self.assertEqual(self.server.protocol_factory.config, self.config)
        self.assertEqual(self.server.protocol_factory.app, self.app)

    def test_init_default(self):
        with self.assertRaises(Exception):
            self.server = AbstractServer(None)

    def test_dispose(self):
        self.server.stop = Mock()
        self.server.protocol_factory.dispose = factory_dispose = Mock()

        self.server.dispose()

        self.server.stop.assert_called_once()
        factory_dispose.assert_called_once()
        self.assertIsNone(self.server.config)
        self.assertIsNone(self.server.protocol_factory)

    def test_start(self, server_mock=None):
        # (NotImplemented is unavailable)
        with self.assertRaises(Exception):
            self.server.start()

    def test_stop(self):
        # (NotImplemented is unavailable)
        with self.assertRaises(Exception):
            self.server.stop()


# Twisted

class TestTwistedHandler(TestCase):
    config = ServerConfig("somehost", 12345)
    config.DELIMITER = b"[MYEND]"
    config.protocol_class = Protocol
    app = SocketGameApplication(config)

    def setUp(self):
        super().setUp()
        self.handler = TwistedHandler()
        self.handler.factory = ServerFactory()
        self.handler.factory.config = self.config
        self.handler.factory.protocol_factory = ProtocolFactory(self.config, self.app)
        self.handler.transport = MagicMock(**{"getPeer.return_value": Mock(host="myhost", port=1234)})

    def test_lifetime(self):
        # connectionMade
        self.assertEqual(self.handler.delimiter, b"\x00")

        self.handler.connectionMade()

        self.assertEqual(self.handler.delimiter, b"[MYEND]")
        protocol = self.handler.protocol
        self.assertIsInstance(protocol, Protocol)
        self.assertEqual(protocol.send_bytes_method, self.handler.sendLine)
        self.assertEqual(protocol.close_connection_method, self.handler.transport.loseConnection)
        self.assertEqual(protocol.config, self.config)
        self.assertEqual(protocol.address, ("myhost", 1234))

        # rawDataReceived: check no exception
        self.handler.rawDataReceived(None)

        # lineReceived
        protocol.process_bytes_list = Mock()

        self.handler.lineReceived("my||data||line##")

        self.assertEqual(self.handler.protocol, protocol)
        protocol.process_bytes_list.assert_called_once_with(("my||data||line##",))

        # connectionLost
        protocol.dispose = Mock()

        self.handler.connectionLost()

        protocol.dispose.assert_called_once()
        self.assertIsNone(self.handler.protocol)


class TestTwistedTCPServer(TestAbstractServer):
    config = ServerConfig("somehost", 12345)
    app = SocketGameApplication(config)

    def setUp(self):
        # super().setUp()
        self.server = TwistedTCPServer(self.config, self.app)

    def test_init(self):
        super().test_init()

        self.assertIsNone(TwistedTCPServer.factory)
        self.assertIsInstance(self.server.factory, ServerFactory)
        self.assertEqual(self.server.config, self.config)
        self.assertEqual(self.server.factory.config, self.config)
        self.assertEqual(self.server.factory.protocol, TwistedHandler)
        self.assertEqual(self.server.factory.protocol_factory, self.server.protocol_factory)

    def test_init_default(self):
        with self.assertRaises(Exception):
            TwistedTCPServer(None)

    def test_dispose(self):
        factory = self.server.factory

        super().test_dispose()

        self.assertIsNone(self.server.factory)
        self.assertIsNone(factory.config)
        self.assertIsNone(factory.protocol)
        self.assertIsNone(factory.protocol_factory)

    def test_start(self, server_mock=None):
        reactor.listenTCP = Mock()
        reactor.run = Mock()

        self.server.start()
        # Should skip others without errors
        self.server.start()
        self.server.start()

        reactor.listenTCP.assert_called_once_with(12345, self.server.factory)
        reactor.run.assert_called_once()

    def test_stop(self):
        reactor.stop = Mock()

        self.server.started = True

        self.server.stop()
        # Should skip others without errors
        self.server.stop()
        self.server.stop()

        reactor.stop.assert_not_called()
        # reactor.stop.assert_called_once()


# Threaded

class MyThreadedTCPHandler(ThreadedTCPHandler):
    is_first_handle = True

    def handle(self):
        # Skip handle() invocation from constructor
        if self.is_first_handle:
            self.is_first_handle = False
            return
        super().handle()


class TestThreadedTCPHandler(TestCase):
    address = ("somehost", 12345)
    config = ServerConfig(*address, Protocol)
    app = SocketGameApplication(config)
    protocol_factory = ProtocolFactory(config, app)

    def setUp(self):
        super().setUp()

        self.request = Mock()
        self.request.close = Mock()
        self.server = Mock(protocol_factory=self.protocol_factory, config=self.config, abort=False)

        # temp
        self.server.abort = True
        assert self.server.abort
        self.server.abort = False

        self.handler = MyThreadedTCPHandler(self.request, self.address, self.server)
        self.handler.setup()

    def test_setup(self):
        self.handler = MyThreadedTCPHandler(self.request, self.address, self.server)

        self.assertIsNone(self.handler.protocol)

        self.handler.setup()

        self.assertIsNotNone(self.handler.protocol)
        self.assertIsInstance(self.handler.protocol, Protocol)
        self.assertEqual(self.handler.protocol.send_bytes_method, self.handler.send_bytes)
        self.assertEqual(self.handler.protocol.close_connection_method, self.request.close)
        self.assertEqual(self.handler.protocol.address, self.address)

    def test_finish(self):
        self.handler.protocol.dispose = dispose_protocol = Mock()

        self.handler.finish()

        dispose_protocol.assert_called_once()
        self.assertIsNone(self.handler.protocol)

    def test_send_bytes(self):
        self.request.sendall = Mock()

        self.handler.send_bytes(b"some_bytes")

        self.request.sendall.assert_called_once_with(b"some_bytes\x00")

    def test_handle(self):
        # Connection lost on recv() returns empty
        self.request.recv = Mock(side_effect=[
            b"1||param1||",
            b"param2##\x002||param1||param2##\x00",
            b"3||", b"param1||", b"param2##\x00",
            b"4||param1||param2##\x00",
            b"",
            b"5||param1||param2##\x00"
        ])
        self.handler.protocol.process_bytes_list = process_bytes_list_mock = Mock()

        self.handler.handle()

        self.assertEqual(process_bytes_list_mock.call_args_list, [
            call([b"1||param1||param2##", b"2||param1||param2##"]),
            call([b"3||param1||param2##"]),
            call([b"4||param1||param2##"])
        ])

    def test_handle__abort(self):
        # Stop on abort (on b"4||..." message)
        process_bytes_list_mock = Mock()

        def do_abort(data_bytes_list):
            process_bytes_list_mock(data_bytes_list)
            if data_bytes_list == [b"4||param1||param2##"]:
                self.server.abort = True

        self.request.recv = Mock(side_effect=[
            b"3||", b"param1||", b"param2##\x00",
            b"4||param1||param2##\x00",
            b"5||param1||param2##\x00"
        ])
        self.handler.protocol.process_bytes_list = do_abort

        self.handler.handle()

        self.assertEqual(process_bytes_list_mock.call_args_list, [
            call([b"3||param1||param2##"]),
            call([b"4||param1||param2##"])
        ])

    def test_handle__recv_raises_exception(self):
        # Connection lost on recv() raises socket.error
        self.request.recv = Mock(side_effect=[
            b"3||", b"param1||", b"param2##\x00",
            b"4||param1||param2##\x00",
            socket.error,
            b"5||param1||param2##\x00"
        ])
        self.handler.protocol.process_bytes_list = process_bytes_list_mock = Mock(
            side_effect={b"4||param1||param2##": socket.error})

        self.handler.handle()

        self.assertEqual(process_bytes_list_mock.call_args_list, [
            call([b"3||param1||param2##"]),
            call([b"4||param1||param2##"])
        ])

    def test_handle__process_raises_exception(self):
        # Connection lost on protocol.process_bytes_list() raises exception
        self.request.recv = Mock(side_effect=[
            b"3||", b"param1||", b"param2##\x00",
            b"4||param1||param2##\x00",
            b"5||param1||param2##\x00"
        ])

        def do_raise(data_bytes_list):
            if data_bytes_list == [b"4||param1||param2##"]:
                raise MySpecificException

        self.handler.protocol.process_bytes_list = Mock(side_effect=do_raise)

        self.handler.handle()

        self.assertEqual(self.handler.protocol.process_bytes_list.call_args_list, [
            call([b"3||param1||param2##"]),
            call([b"4||param1||param2##"])
        ])

        # def do_test_handle(self, recv_mock, process_bytes_list_mock, expected_call_args_list):
        #     self.request.recv = recv_mock
        #
        #     self.handler.protocol.process_bytes_list = process_bytes_list_mock
        #
        #     self.handler.handle()
        #
        #     self.assertEqual(self.handler.protocol.process_bytes_list.call_args_list, expected_call_args_list)


class MyThreadingTCPServer(socketserver.ThreadingTCPServer):
    started_event = Event()

    def serve_forever(self, poll_interval=0.5):
        self.started_event.set()
        super().serve_forever(poll_interval)


class TestThreadedTCPServer(TestAbstractServer):
    address = ("localhost", 12345)
    config = ServerConfig(*address, Protocol)
    app = SocketGameApplication(config)

    def setUp(self):
        # super().setUp()

        # For test_start_stop()
        patcher = patch("socketserver.ThreadingTCPServer", MyThreadingTCPServer)
        self.addCleanup(patcher.stop)
        patcher.start()

        self.server = ThreadedTCPServer(self.config, self.app)

    def test_init_default(self):
        with self.assertRaises(Exception):
            ThreadedTCPServer(None)

    @patch("socketserver.ThreadingTCPServer")
    def test_start(self, server_mock=None):
        self.server.start()
        # Should skip others without errors
        self.server.start()
        self.server.start()

        self.assertEqual(server_mock.mock_calls[0], call(self.address, ThreadedTCPHandler))
        self.assertEqual(server_mock.mock_calls[1], call().serve_forever())
        self.assertEqual(server_mock.mock_calls[2], call().server_close())
        # Should be cleared after serving ended
        self.assertTrue(server_mock.return_value.abort)
        self.assertIsNone(server_mock.return_value.protocol_factory)
        self.assertIsNone(server_mock.return_value.config)
        self.assertIsNone(self.server.server)

    def test_stop(self):
        # No exception
        self.assertIsNone(self.server.server)

        self.server.stop()

        # Check shutdown() called
        self.server.server = MagicMock()
        self.server.started = True

        self.server.stop()
        # Should skip others without errors
        self.server.stop()
        self.server.stop()

        self.server.server.shutdown.assert_called_once()

    def test_start_stop(self):
        MyThreadingTCPServer.started_event.clear()

        # Start server
        thread = Thread(target=self.server.start)
        thread.start()
        # Should skip others without errors
        self.server.start()
        self.server.start()

        MyThreadingTCPServer.started_event.wait()

        self.assertIsNotNone(self.server.server)
        self.assertFalse(self.server.server.abort)
        self.assertEqual(self.server.server.protocol_factory, self.server.protocol_factory)
        self.assertEqual(self.server.server.config, self.config)

        threading_server = self.server.server

        self.server.stop()
        # Should skip others without errors
        self.server.stop()
        self.server.stop()

        # Should be cleared after serving ended
        self.assertTrue(threading_server.abort)
        self.assertIsNone(threading_server.protocol_factory)
        self.assertIsNone(threading_server.config)
        self.assertIsNone(self.server.server)

        thread.join()


# Non-blocking

class MySocket(socket.socket):
    def accept(self):
        raise socket.error


class MyNonBlockingTCPServer(NonBlockingTCPServer):
    started_event = Event()

    def _workflow(self, sock):
        self.started_event.set()
        super()._workflow(sock)


class MyWouldBlockSocketError(socket.error):
    errno = errno.EWOULDBLOCK


class MyProtocol(SimpleProtocol):
    disposed_count = 0

    def dispose(self):
        super().dispose()
        MyProtocol.disposed_count += 1


class TestNonBlockingTCPServer(TestAbstractServer):
    address = ("localhost", 12345)
    config = ServerConfig(*address, Protocol)
    app = SocketGameApplication(config)

    def setUp(self):
        # super().setUp()

        # # For test_start_stop()
        # patcher = patch("napalm.socket.server.NonBlockingTCPServer", MyNonBlockingTCPServer)
        # self.addCleanup(patcher.stop)
        # patcher.start()

        self.server = MyNonBlockingTCPServer(self.config, self.app)

    def test_init_default(self):
        with self.assertRaises(Exception):
            NonBlockingTCPServer(None)

    @patch("socket.socket")
    def test_start(self, sock_mock=None):
        # Skipping workflow loop
        self.server._workflow = Mock()
        # Simulate workflow activity
        protocol = MagicMock()
        self.server._request_by_protocol = {protocol: Mock()}
        self.server._buffer_by_protocol = {protocol: b"data"}
        self.server._protocol_list = [protocol]

        self.server.start()
        # Should skip others without errors
        self.server.start()
        self.server.start()

        self.assertEqual(sock_mock.mock_calls[0], call(socket.AF_INET, socket.SOCK_STREAM))
        self.assertEqual(sock_mock.mock_calls[1], call().setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1))
        self.assertEqual(sock_mock.mock_calls[2], call().bind(self.address))
        self.assertEqual(sock_mock.mock_calls[3], call().listen())
        self.assertEqual(sock_mock.mock_calls[4], call().setblocking(0))
        self.assertEqual(sock_mock.mock_calls[5], call().shutdown(socket.SHUT_RDWR))
        self.assertEqual(sock_mock.mock_calls[6], call().close())
        # Should be cleared after serving ended
        self.assertIsNone(self.server._sock)
        protocol.dispose.assert_called_once()
        self.assertEqual(self.server._protocol_list, [])
        self.assertEqual(self.server._request_by_protocol, {})
        self.assertEqual(self.server._buffer_by_protocol, {})

    def test_stop(self):
        self.assertFalse(self.server._abort)

        self.server.started = True

        self.server.stop()
        # Should skip others without errors
        self.server.stop()
        self.server.stop()

        self.assertTrue(self.server._abort)

    def test_start_stop(self):
        MyNonBlockingTCPServer.started_event.clear()

        # Start server
        thread = Thread(target=self.server.start)
        thread.start()
        # Should skip others without errors
        self.server.start()
        self.server.start()

        # Wait until server started (workflow began)
        MyNonBlockingTCPServer.started_event.wait()

        self.assertFalse(self.server._abort)
        self.assertIsNotNone(self.server._sock)
        self.assertEqual(self.server._sock.getsockname(), ("127.0.0.1", self.address[1]))

        sock = self.server._sock

        self.server.stop()
        # Should skip others without errors
        self.server.stop()
        self.server.stop()

        # Should be cleared after serving ended
        self.assertTrue(self.server._abort)
        self.assertIsNone(self.server._sock)
        with self.assertRaises(OSError):
            # Error means socket closed
            # (OSError: [WinError 10038] Сделана попытка выполнить операцию на объекте, не являющемся сокетом)
            self.assertIsNone(sock.getsockname())
        # Check non-blocking (None - for blocking)
        self.assertEqual(sock.timeout, 0)

        thread.join()

    def test_workflow(self):
        requests = [MagicMock(), MagicMock(), MagicMock()]
        protocols = [MyProtocol(), MyProtocol(), MyProtocol(), MyProtocol()]

        # Set up data received by request and processed by protocol
        # (Connection lost on recv() returns empty)
        requests[0].recv = Mock(side_effect=[
            b"1||param1||",
            MyWouldBlockSocketError,
            b"param2##\x002||param1||param2##\x00",
            MyWouldBlockSocketError,
            b"3||", b"param1||", b"param2##\x00",
            MyWouldBlockSocketError,
            b"4||param1||param2##\x00",
            b"",
            b"5||param1||param2##\x00"
        ])
        protocols[0].process_bytes_list = Mock()

        # (Connection lost on recv() raises socket.error)
        requests[1].recv = Mock(side_effect=[
            b"6||", b"param1||", b"param2##\x00",
            MyWouldBlockSocketError,
            b"7||param1||param2##\x00",
            # (In our server implementation we suggest that error could not occur before
            # between blocking if we've already received some data.
            # So we place MyWouldBlockSocketError before socket.error.)
            MyWouldBlockSocketError,
            socket.error,
            b"8||param1||param2##\x00"
        ])
        # protocols[1].process_bytes_list = Mock(
        #     side_effect={b"4||param1||param2##": socket.error})
        protocols[1].process_bytes_list = Mock()

        # (Connection lost on protocol.process_bytes_list() raises exception)
        requests[2].recv = Mock(side_effect=[
            b"9||", b"param1||", b"param2##\x00",
            MyWouldBlockSocketError,
            b"10||param1||param2##\x00",
            MyWouldBlockSocketError,
            b"11||param1||param2##\x00"
        ])

        def do_raise(data_bytes_list):
            if data_bytes_list == [b"10||param1||param2##"]:
                raise MySpecificException

        protocols[2].process_bytes_list = Mock(side_effect=do_raise)

        # Expected results
        expected_call_args_list = [[
            call([b"1||param1||param2##", b"2||param1||param2##"]),
            call([b"3||param1||param2##"]),
            call([b"4||param1||param2##"])
        ], [
            call([b"6||param1||param2##"]),
            call([b"7||param1||param2##"])
        ], [
            call([b"9||param1||param2##"]),
            call([b"10||param1||param2##"])
        ], [
            # Current protocol is not used
        ]]

        self.do_test_workflow(requests, protocols, expected_call_args_list)

        # todo assert instances in protocol_list and lookups

    def test_workflow_with_abort(self):
        requests = [MagicMock(), MagicMock()]
        protocols = [MyProtocol(), MyProtocol(), MyProtocol()]

        # Set up data received by request and processed by protocol
        # (Connection lost on recv() returns empty)
        requests[0].recv = Mock(side_effect=[
            b"1||param1||",
            MyWouldBlockSocketError,
            b"param2##\x002||param1||param2##\x00",
            MyWouldBlockSocketError,
            b"3||", b"param1||", b"param2##\x00",
            MyWouldBlockSocketError,
            b"4||param1||param2##\x00",
            b"",
            b"5||param1||param2##\x00"
        ])

        protocols[0].process_bytes_list = Mock()

        # (Connection lost on recv() raises socket.error)
        requests[1].recv = Mock(side_effect=[
            b"6||", b"param1||", b"param2##\x00",
            MyWouldBlockSocketError,
            b"7||param1||param2##\x00",
            MyWouldBlockSocketError,
            b"8||param1||param2##\x00"
        ])

        def do_abort(data_bytes_list):
            if data_bytes_list == [b"7||param1||param2##"]:
                self.server._abort = True
        protocols[1].process_bytes_list = Mock(side_effect=do_abort)

        # Expected results
        expected_call_args_list = [[
            call([b"1||param1||param2##", b"2||param1||param2##"]),
            call([b"3||param1||param2##"]),
            # call([b"4||param1||param2##"])
        ], [
            call([b"6||param1||param2##"]),
            call([b"7||param1||param2##"])
            # Aborted
        ], [
            # Current protocol is not used
        ]]

        self.do_test_workflow(requests, protocols, expected_call_args_list)

        # todo assert instances in protocol_list and lookups

    def do_test_workflow(self, requests, protocols, expected_call_args_list):
        # (All process_bytes_list methods should be mocked)
        for protocol in protocols:
            if not isinstance(protocol.process_bytes_list, Mock):
                protocol.process_bytes_list = Mock()

        # Set up connections
        # (Accepting connection and creating protocol for each)
        sock = MagicMock()
        accept_list = list([(request, ("somehost", random.randint(1000, 60000))) for request in requests])
        accept_list.append(socket.error)
        accept_list.insert(0, socket.error)
        sock.accept.side_effect = accept_list
        self.server.protocol_factory.create = Mock(side_effect=protocols)

        # Start
        MyProtocol.disposed_count = 0
        thread = Thread(target=self.server._workflow, args=[sock])
        thread.start()

        # Wait until all protocol disposed to abort workflow
        # (Note: we take len(requests), because len(protocols) could be > len(requests))
        while MyProtocol.disposed_count < len(requests) and not self.server._abort:
            pass
        self.server._abort = True
        # thread.join()

        # Assert
        for index, expected_call_args in enumerate(expected_call_args_list):
            actual_call_args = protocols[index].process_bytes_list.call_args_list
            self.assertEqual(actual_call_args, expected_call_args)
