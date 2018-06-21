import socket
from threading import Thread
from unittest import TestCase
from unittest.mock import Mock, patch, call, MagicMock

from twisted.internet.protocol import ClientFactory

import napalm
from napalm.socket import client
from napalm.socket.client import ClientConfig, AbstractClient, BlockingTCPClient, TwistedTCPClient, ThreadedTCPClient
from napalm.socket.server import Config, ProtocolFactory, TwistedHandler


class TestClientConfig(TestCase):
    def test_inheritance(self):
        self.assertIsInstance(ClientConfig(), Config)


class TestAbstractClient(TestCase):
    config = ClientConfig()
    client_class = AbstractClient
    client = None

    def setUp(self):
        super().setUp()

        self.client = self.client_class(self.config, "app_stub")

    def test_init(self):
        # config
        self.assertEqual(self.client.config, self.config)
        # protocol_factory
        self.assertIsNotNone(self.client.protocol_factory)
        self.assertIsInstance(self.client.protocol_factory, ProtocolFactory)
        self.assertEqual(self.client.protocol_factory.config, self.config)
        self.assertEqual(self.client.protocol_factory.app, "app_stub")

        # Test without arguments
        # No exception
        self.client = self.client_class()

        # config
        self.assertIsNotNone(self.client.config)
        self.assertIsInstance(self.client.config, ClientConfig)
        # protocol_factory
        self.assertIsNotNone(self.client.protocol_factory)
        self.assertIsInstance(self.client.protocol_factory, ProtocolFactory)
        self.assertEqual(self.client.protocol_factory.config, self.client.config)
        self.assertIsNone(self.client.protocol_factory.app)

    def test_dispose(self):
        self.client.close = Mock()
        self.client.protocol_factory.dispose = factory_dispose = Mock(side_effect=self.client.protocol_factory.dispose)

        self.client.dispose()

        self.client.close.assert_called_once()
        factory_dispose.assert_called_once()
        self.assertIsNone(self.client.config)
        self.assertIsNone(self.client.protocol_factory)

    def test_connect(self):
        with self.assertRaises(Exception):
            self.client.connect()

    def test_close(self):
        with self.assertRaises(Exception):
            self.client.close()

    # def test_data_received(self):
    #     with self.assertRaises(Exception):
    #         self.client.data_received()
    # 
    # def test_send_raw(self):
    #     with self.assertRaises(Exception):
    #         self.client.send_raw()


class TestTwistedTCPClient(TestAbstractClient):
    client_class = TwistedTCPClient

    def test_init(self):
        self.assertIsInstance(self.client.factory, ClientFactory)
        self.assertEqual(self.client.factory.config, self.config)
        self.assertEqual(self.client.factory.protocol, TwistedHandler)
        self.assertIsNotNone(self.client.factory.protocol_factory)
        self.assertEqual(self.client.factory.protocol_factory, self.client.protocol_factory)

    def test_dispose(self):
        factory = self.client.factory

        self.client.dispose()

        self.assertIsNone(self.client.factory)
        self.assertIsNone(factory.config)
        # self.assertIsNone(factory.protocol)
        self.assertIsNone(factory.protocol_factory)

    def test_connect(self):
        reactor = MagicMock()
        reactor.running = False
        napalm.socket.client.reactor = reactor

        self.client.connect()

        reactor.connectTCP.assert_called_once_with(self.config.host, self.config.port, self.client.factory)
        reactor.run.assert_called_once()

    def test_connect2(self):
        reactor = MagicMock()
        reactor.running = True
        address = ("anotherhost", "anotherport")
        napalm.socket.client.reactor = reactor

        self.client.connect(address)

        reactor.connectTCP.assert_called_once_with("anotherhost", "anotherport", self.client.factory)
        reactor.run.assert_not_called()

    def test_close(self):
        # No exception
        self.client.connector = None
        self.client.on_close = None

        self.client.dispose()

        # Dispose
        self.client.connector = connector = MagicMock()
        self.client.on_close = Mock()

        self.client.dispose()

        self.assertIsNone(self.client.connector)
        connector.disconnect.assert_called_once()
        self.client.on_close.assert_called_once()


class TestBlockingTCPClient(TestAbstractClient):
    client_class = BlockingTCPClient

    def test_init(self):
        super().test_init()

        self.assertFalse(self.client.connecting)
        self.assertFalse(self.client.connected)

    # @patch("napalm.socket.test.test_client.socket.socket", spec=True)
    def test_connect(self):
        with patch("socket.socket", socket.socket) as conn:
            self.assertFalse(self.client.connecting)
            self.assertFalse(self.client.connected)

            # Set up
            self.client.abort = True

            # (Connecting)
            def conn_connect(server_address):
                self.assertEqual(server_address, (self.config.host, self.config.port))
                # Assert connecting...
                self.assertFalse(self.client.abort)
                self.assertTrue(self.client.connecting)
                self.assertFalse(self.client.connected)
            conn.connect = Mock(side_effect=conn_connect)

            # (Connected)
            def protocol_factory_create(send_raw, close, address):
                self.assertEqual(send_raw, self.client.send_raw)
                self.assertEqual(close, self.client.close)
                self.assertEqual(address, ("local_host", "local_port"))
                # Assert connected
                self.assertFalse(self.client.connecting)
                self.assertTrue(self.client.connected)
                return protocol

            conn.getsockname = Mock(return_value=("local_host", "local_port"))
            # --self.assertEqual(conn.getsockname(), ("local_host", "local_port"))
            protocol = MagicMock()
            self.client.protocol_factory.create = Mock(side_effect=protocol_factory_create)
            self.client.on_connect = Mock()

            def abort_client():
                # (Assert abort was set to False on connect())
                self.assertFalse(self.client.abort)
                self.assertIsNotNone(self.client.protocol)
                self.client.abort = True
            self.client.on_reconnect = Mock(side_effect=abort_client)

            self.client._workflow = Mock()
            # (Disconnected or aborted)
            conn.shutdown = Mock()
            conn.close = Mock()
            self.client.on_close = Mock()

            # Call
            self.client.connect(max_tries=1)
            # self.client.connect()
            # self.client.connect()

            # Assert
            # (Assert conn.connect() was called 2 times)
            self.assertEqual(len(conn.connect.call_args_list), 2)
            self.client.protocol_factory.create.assert_called_once()
            self.assertEqual(len(self.client._workflow.call_args_list), 2)
            # (Disconnected or aborted)
            conn.shutdown.assert_called_with(socket.SHUT_RDWR)
            self.assertEqual(len(conn.shutdown.call_args_list), 2)
            self.assertEqual(len(conn.close.call_args_list), 2)
            self.assertEqual(len(self.client.on_close.call_args_list), 2)
            # Disposed
            protocol.dispose.assert_called_once()
            self.assertIsNone(self.client.protocol)

            self.assertIsNone(self.client.address)
            self.assertIsNone(self.client.conn)

            self.assertFalse(self.client.connecting)
            self.assertFalse(self.client.connected)

    def test_connect_skip(self):
        with patch("socket.socket") as conn:
            self.client.connecting = True
            self.client.connected = False

            self.client.connect()

            conn.connect.assert_not_called()

            self.client.connecting = False
            self.client.connected = True

            self.client.connect()

            conn.connect.assert_not_called()

    def test_close(self):
        # While connecting
        self.client.abort = False
        self.client.connecting = True
        self.client.connected = False

        self.client.close()

        self.assertTrue(self.client.abort)

        # While connected
        self.client.abort = False
        self.client.connecting = False
        self.client.connected = True

        self.client.close()

        self.assertTrue(self.client.abort)

        # No exception
        self.client.close()

    def test_close_skip(self):
        # No connect
        self.client.abort = False
        self.client.connecting = False
        self.client.connected = False

        self.client.close()

        self.assertFalse(self.client.abort)

        # No exception
        self.client.close()

    def test_workflow(self):
        pass

    def test_data_received(self):
        # No exception
        self.assertIsNone(self.client.protocol)

        self.client.data_received([b"aaa", b"bbb"])

        # Normal
        self.client.protocol = MagicMock()

        self.client.data_received([b"aaa", b"bbb"])

        self.client.protocol.process_bytes_list.assert_called_once_with([b"aaa", b"bbb"])

    def test_send_raw(self):
        self.client.conn = MagicMock()

        # Empty
        self.client.send_raw(None)
        self.client.send_raw(b"")

        self.assertEqual(self.client.conn.call_count, 0)

        # Normal
        self.client.send_raw(b"data1")
        self.client.send_raw(b"data2\x00")

        self.assertEqual(self.client.conn.send.call_count, 2)
        self.assertEqual(self.client.conn.send.call_args_list, [
            call(b"data1\x00"),
            call(b"data2\x00"),
        ])

        # Buffer and resend on fail
        # self.client.conn.send = Mock(side_effect=[socket.error, None])
        # self.client.conn.send = Mock(side_effect=[socket.error, socket.error])
        self.client.conn.send = Mock(side_effect=[socket.error])

        with self.assertRaises(Exception):
            self.client.send_raw(b"data1")
            # self.client.send_raw(b"data2\x00")

        # self.assertEqual(self.client.conn.send.call_count, 2)
        # # self.assertEqual(self.client.conn.send.call_args_list, [
        # #     call(b"data1\x00"),
        # #     call(b"data1\x00data2\x00"),
        # # ])
        # self.assertEqual(self.client.sending_buffer, b"data1\x00data2\x00")


class TestThreadedTCPClient(TestCase):

    def test_inheritance(self):
        self.client = ThreadedTCPClient()

        self.assertIsInstance(self.client, BlockingTCPClient)
        self.assertIsInstance(self.client, Thread)

    def test_run(self):
        self.client = ThreadedTCPClient()
        self.client.address = ("myhost", "myport")
        self.client.max_tries = 17.5
        self.client.try_interval = 19.5
        self.client.connect = Mock()

        self.client.run()

        self.client.connect.assert_called_once_with(("myhost", "myport"), 17.5, 19.5)
