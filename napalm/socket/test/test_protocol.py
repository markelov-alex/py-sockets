from unittest import TestCase
from unittest.mock import Mock, MagicMock, call

from napalm.socket.parser import CommandParser
from napalm.socket.protocol import Protocol, SimpleProtocol, ProtocolPlugin
from napalm.socket.server import ServerConfig


class TestSimpleProtocol(TestCase):
    def setUp(self):
        super().setUp()

        self.protocol = SimpleProtocol()

    def test_init(self):
        class MySimpleProtocol(SimpleProtocol):
            def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
                self.on_connect = Mock()
                super().__init__(send_bytes_method, close_connection_method, address, config, app)

        self.protocol = MySimpleProtocol("send_bytes_method", "close_connection_method", "address", "config", None)

        self.assertEqual(self.protocol.send_bytes_method, "send_bytes_method")
        self.assertEqual(self.protocol.close_connection_method, "close_connection_method")
        self.assertEqual(self.protocol.address, "address")
        self.assertEqual(self.protocol.config, "config")
        self.protocol.on_connect.assert_called_once()

        # (on_connect not called if send_bytes_method not set)
        self.protocol = MySimpleProtocol()

        self.protocol.on_connect.assert_not_called()

    def test_dispose(self):
        # Normal
        self.protocol.send_bytes_method = {"some": "object"}
        self.protocol.close_connection_method = close_connection_method = Mock()
        self.protocol.on_disconnect = Mock()
        self.protocol.address = {"some": "object"}

        self.protocol.dispose()

        close_connection_method.assert_called_once()
        self.protocol.on_disconnect.assert_called_once()
        self.assertEqual(self.protocol.send_bytes_method, None)
        self.assertEqual(self.protocol.close_connection_method, None)
        self.assertEqual(self.protocol.address, None)
        self.assertEqual(self.protocol.config, None)

    # Send

    def test_send_raw(self):
        # Not initialized protocol - assert no exception
        self.protocol.send_bytes_method = None
        self.protocol.send_raw("")

        self.protocol.send_bytes_method = Mock()

        # Empty
        self.protocol.send_raw("")

        # Normal
        self.protocol.send_bytes_method.assert_not_called()

        self.protocol.send_raw("data##")
        self.protocol.send_raw(b"data2##")

        self.assertEqual(self.protocol.send_bytes_method.call_args_list,
                         [call(b"data##",), call(b"data2##",)])

    def test_send_all_raw(self):
        self.protocol.config = Mock(**{"RECV_SIZE": 14})  # , "DELIMITER": b"%%"
        # Not initialized protocol - assert no exception
        self.protocol.send_bytes_method = None
        self.protocol.send_all_raw("")

        # Empty
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_all_raw("")

        self.protocol.send_bytes_method.assert_not_called()

        # Normal - str
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_all_raw(["data1##", b"data2##", "data3##", b"data10##"])

        self.assertEqual(self.protocol.send_bytes_method.call_args_list,
                         [call(b"data1##data2##",), call(b"data3##",), call(b"data10##",)])

    # Process
    def test_on_connect(self):
        # Assert no exception
        self.protocol.on_connect()

    def test_on_disconnect(self):
        # Assert no exception
        self.protocol.on_disconnect()

    def test_process_bytes_list(self):
        self.protocol.process_bytes = Mock()

        # None, empty
        self.protocol.process_bytes_list(None)
        self.protocol.process_bytes_list([])

        self.protocol.process_bytes.assert_not_called()

        # Normal
        self.protocol.process_bytes_list([b"data1", b"data2"])

        self.assertEqual(self.protocol.process_bytes.call_args_list,
                         [call(b"data1",), call(b"data2",)])

    def test_process_bytes(self):
            # Assert no exception
            self.protocol.process_bytes(None)


class TestProtocol(TestCase):
    def setUp(self):
        super().setUp()

        self.default_parser_class = Protocol.parser_class

        self.protocol = Protocol(Mock())

    def tearDown(self):
        Protocol.parser_class = self.default_parser_class
        Protocol.parser = None

        super().tearDown()

    def test_is_ready(self):
        self.protocol = Protocol()

        self.assertFalse(self.protocol.is_ready)

        self.protocol = Protocol("send_bytes_method")

        self.assertTrue(self.protocol.is_ready)

    def test_init(self):
        class MyProtocol(Protocol):
            def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
                self.instantiate_plugins = Mock()
                super().__init__(send_bytes_method, close_connection_method, address, config, app)

        last_protocol_id = Protocol.last_protocol_id

        self.protocol = MyProtocol()

        self.assertEqual(Protocol.last_protocol_id, last_protocol_id + 1)
        self.assertEqual(self.protocol.protocol_id, last_protocol_id + 1)
        self.assertEqual(self.protocol.player, None)
        # Assert default config created
        self.assertIsInstance(self.protocol.config, ServerConfig)
        self.assertIsInstance(self.protocol.parser, CommandParser)
        self.assertEqual(self.protocol.parser_class, CommandParser)
        self.protocol.instantiate_plugins.assert_called_once()
        self.assertEqual(self.protocol.is_send_on_flush, False)
        self.assertEqual(self.protocol.deferred_bytes_list, [])

    def test_init(self):
        class MyProtocol(Protocol):
            def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
                self.instantiate_plugins = Mock()
                super().__init__(send_bytes_method, close_connection_method, address, config, app)

        last_protocol_id = Protocol.last_protocol_id

        self.protocol = MyProtocol()

    def test_dispose(self):
        # Normal
        self.protocol.config = ServerConfig()
        self.protocol.flush = Mock()
        self.protocol.plugins = [ProtocolPlugin()]
        self.protocol.plugins[0].dispose = plugin_dispose = Mock(side_effect=self.protocol.plugins[0].dispose)
        self.protocol.player = player = MagicMock()
        player.dispose = Mock(side_effect=player.dispose)
        self.protocol.parser = {"some": "object"}

        self.protocol.dispose()

        self.protocol.flush.assert_called_once()
        self.assertEqual(len(self.protocol.plugins), 0)
        plugin_dispose.assert_called_once()
        self.assertEqual(player.protocol, None)
        self.assertEqual(self.protocol.player, None)
        self.assertEqual(self.protocol.config, None)
        self.assertEqual(self.protocol.parser, None)
        player.dispose.assert_not_called()

        # Call again: Assert no exception when all are None
        self.protocol.dispose()

        # With other config (is_continue_on_disconnect=True)
        player = Mock()
        player.protocol = "my_protocol_object"
        self.protocol.config = Mock()
        self.protocol.config.is_continue_on_disconnect = True
        self.protocol.player = player

        self.protocol.dispose()

        self.assertEqual(player.protocol, None)
        self.assertEqual(player.protocol, Protocol.dummy_protocol)

        # With other config (is_continue_on_disconnect=False)
        player = Mock()
        player.protocol = "my_protocol_object"
        self.protocol.config = Mock()
        self.protocol.config.is_continue_on_disconnect = False
        self.protocol.player = player

        self.protocol.dispose()

        self.assertEqual(player.protocol, None)

    def test_instantiate_plugins(self):
        # Init
        class MyProtocol(Protocol):
            plugins = [ProtocolPlugin, ProtocolPlugin(), None]

        self.protocol = MyProtocol()

        # (Ensure plugins list length not changed)
        self.assertEqual(len(self.protocol.plugins), 2)
        self.assertIsInstance(self.protocol.plugins[0], ProtocolPlugin)
        self.assertIsInstance(self.protocol.plugins[1], ProtocolPlugin)

    # Send
    def test_set_send_on_flush(self):
        self.protocol.is_send_on_flush = False

        self.protocol.set_send_on_flush()

        self.assertEqual(self.protocol.is_send_on_flush, True)

    def test_flush(self):
        # Normal
        self.protocol.set_send_on_flush()
        self.protocol.send("cmd1")
        self.protocol.send_raw("cmd2")
        self.protocol.send_raw(b"cmd2")
        self.protocol.send_all(["cmd3", "cmd4"])
        self.protocol.send_all_raw(["cmd5", b"cmd6"])
        self.protocol.send_all_raw = Mock()
        self.protocol.send_bytes_method = Mock()

        self.protocol.flush()

        self.assertEqual(self.protocol.is_send_on_flush, False)
        self.assertEqual(self.protocol.deferred_bytes_list, [])
        self.protocol.send_all_raw.assert_called_once_with(
            [b"cmd1##", "cmd2", b"cmd2", b"cmd3##", b"cmd4##", "cmd5", b"cmd6"])

        # Same with is_send_on_flush = False
        self.protocol.send_all_raw.reset_mock()
        self.protocol.is_send_on_flush = False
        self.protocol.deferred_bytes_list = ["command1", b"command2"]

        self.protocol.flush()

        self.assertEqual(self.protocol.is_send_on_flush, False)
        self.assertEqual(self.protocol.deferred_bytes_list, [])
        self.protocol.send_all_raw.assert_called_once_with(["command1", b"command2"])

        # Skip sends if not initialized
        self.protocol.send_bytes_method = None
        self.protocol.set_send_on_flush()
        self.protocol.send("cmd1")
        self.protocol.send_raw(b"cmd2")
        self.protocol.send_all(["cmd3", "cmd4"])
        self.protocol.send_all_raw(["cmd5", b"cmd6"])
        self.protocol.send_all_raw = Mock()

        self.assertEqual(self.protocol.deferred_bytes_list, [])

    def test_send(self):
        # Not initialized protocol: no exception
        self.protocol.send_bytes_method = None
        self.protocol.send([])

        # Normal
        self.protocol.send_bytes_method = Mock()

        self.protocol.send(["1", "param1", "param2"])
        self.protocol.send("2||param1||param2")

        self.assertEqual(self.protocol.send_bytes_method.call_args_list, 
                         [call(b"1||param1||param2##"),
                          call(b"2||param1||param2##")])

        # Deferred
        self.protocol.set_send_on_flush()
        self.protocol.send_bytes_method = Mock()

        self.protocol.send(["1", "param1", "param2"])
        self.protocol.send("2||param1||param2")

        self.assertEqual(self.protocol.deferred_bytes_list,
                         [b"1||param1||param2##",
                          b"2||param1||param2##"])
        self.protocol.send_bytes_method.assert_not_called()

    def test_send_all(self):
        # Not initialized protocol: no exception
        self.protocol.send_bytes_method = None
        self.protocol.send_all([])

        # Normal
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_all([["1", "param1", "param2"], "2||param1||param2"])

        self.protocol.send_bytes_method.assert_called_once_with(b"1||param1||param2##2||param1||param2##")

        # Deferred
        self.protocol.set_send_on_flush()
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_all([["1", "param1", "param2"], "2||param1||param2"])

        self.assertEqual(self.protocol.deferred_bytes_list,
                         [b"1||param1||param2##", b"2||param1||param2##"])
        self.protocol.send_bytes_method.assert_not_called()

    def test_send_raw(self):
        # Normal
        # see TestSimpleProtocol

        # Deferred
        self.protocol.set_send_on_flush()
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_raw(b"1||param1||param2##")
        self.protocol.send_raw("2||param1||param2##")

        self.assertEqual(self.protocol.deferred_bytes_list,
                         [b"1||param1||param2##",
                          "2||param1||param2##"])
        self.protocol.send_bytes_method.assert_not_called()

    def test_send_all_raw(self):
        # Normal
        # see TestSimpleProtocol

        # Deferred
        self.protocol.set_send_on_flush()
        self.protocol.send_bytes_method = Mock()

        self.protocol.send_all_raw([b"1||param1||param2##", "2||param1||param2##"])

        self.assertEqual(self.protocol.deferred_bytes_list,
                         [b"1||param1||param2##", "2||param1||param2##"])
        self.protocol.send_bytes_method.assert_not_called()

    # Process
    def test_on_connect(self):
        self.protocol.plugins = [MagicMock(), MagicMock()]

        self.protocol.on_connect()

        for plugin in self.protocol.plugins:
            plugin.on_connect.assert_called_once()
        # (Ensure plugins list is not empty)
        self.assertEqual(len(self.protocol.plugins), 2)

    def test_on_disconnect(self):
        self.protocol.plugins = [MagicMock(), MagicMock()]

        self.protocol.on_disconnect()

        for plugin in self.protocol.plugins:
            plugin.on_disconnect.assert_called_once()
        # (Ensure plugins list is not empty)
        self.assertEqual(len(self.protocol.plugins), 2)

    def test_process_bytes_list(self):
        self.protocol.set_send_on_flush = Mock()
        self.protocol.process_bytes = Mock()
        self.protocol.flush = Mock()

        self.protocol.process_bytes_list([b"1||param1||param2##111||param3||param4####",
                                          b"##4||param5||param6##"])

        self.protocol.set_send_on_flush.assert_called_once()
        self.assertEqual(self.protocol.process_bytes.call_args_list,
                         [call(b"1||param1||param2##111||param3||param4####"),
                          call(b"##4||param5||param6##")])
        self.protocol.flush.assert_called_once()

    def test_process_bytes_if_auth_not_required(self):
        # (False by default)
        # self.protocol.is_auth_required = False
        self.protocol.authorize_command_to_process = 111
        self.protocol.send = Mock()
        self.protocol._process_auth_command = Mock(return_value=Mock())
        self.protocol._process_command = Mock()

        self.protocol.process_bytes(b"1||param1||param2##111||param3||param4######4||param5||param6##")

        self.protocol.send.assert_not_called()
        # "1||param1||param2##" - processed without authorization
        self.assertEqual(self.protocol._process_command.call_args_list[0], call(1, ["1", "param1", "param2"], 3))
        # "111||param3||param4##" - authorize
        self.protocol._process_auth_command.assert_called_once_with(111, ["111", "param3", "param4"], 3)
        # "4||param5||param6##" - processed
        self.assertEqual(self.protocol._process_command.call_args_list[1], call(4, ["4", "param5", "param6"], 3))

    def test_process_bytes_if_auth_required(self):
        self.protocol.is_auth_required = True
        self.protocol.authorize_command_to_process = 111
        self.protocol.send = Mock()
        self.protocol._process_auth_command = Mock(return_value=Mock())
        self.protocol._process_command = Mock()

        self.protocol.process_bytes(b"1||param1||param2##111||param3||param4######4||param5||param6##")

        # "1||param1||param2##" - ignored
        self.protocol.send.assert_called_once()
        send_call = self.protocol.send.call_args[0][0]
        self.assertEqual(send_call[0], 0)  # to be changed
        self.assertRegex(send_call[1], "not authorized")
        # "111||param3||param4##" - authorize
        self.protocol._process_auth_command.assert_called_once_with(111, ["111", "param3", "param4"], 3)
        # "4||param5||param6##" - processed
        self.protocol._process_command.assert_called_once_with(4, ["4", "param5", "param6"], 3)

    # protected

    def test_parse_command(self):
        # Empty argument
        self.assertEqual(self.protocol._parse_command(""), None)
        self.assertEqual(self.protocol._parse_command(None), None)

        # Policy request
        self.protocol.send_raw = Mock()
        self.assertEqual(self.protocol._parse_command("  <policy-file-request/>  \0"), None)
        self.protocol.send_raw.assert_called_once_with('<?xml version="1.0"?>'
                                                       '<cross-domain-policy>'
                                                       '<allow-access-from domain="*" to-ports="*"/>'
                                                       '</cross-domain-policy>')

        # Regular command
        command_code, command_params, params_count = self.protocol._parse_command("7||zz||bb||cc")
        self.assertEqual(command_code, 7)
        self.assertEqual(command_params, ["7", "zz", "bb", "cc"])
        self.assertEqual(params_count, 4)

    # @unittest.skip("Empty method")
    def test_process_auth_command(self):
        # Test no exception
        self.protocol._process_auth_command(7, ["7", "zz", "bb", "cc"], 4)

    # @unittest.skip("Empty method")
    def test_process_command(self):
        # Test no exception
        self.protocol._process_command(7, ["7", "zz", "bb", "cc"], 4)

        # Test plugins
        self.protocol.plugins = [MagicMock(), MagicMock()]

        self.protocol._process_command(7, ["7", "zz", "bb", "cc"], 4)

        for plugin in self.protocol.plugins:
            plugin.process_command.assert_called_once_with(7, ["7", "zz", "bb", "cc"], 4)
        # (Ensure plugins list is not empty)
        self.assertEqual(len(self.protocol.plugins), 2)

    def testget_command_description(self):
        self.protocol.CLIENT_COMMAND_DESCRIPTION_BY_CODE = {1: "text1"}
        self.protocol.SERVER_COMMAND_DESCRIPTION_BY_CODE = {2: "text2"}

        self.assertEqual(self.protocol.get_command_description(1), "text1")
        self.assertEqual(self.protocol.get_command_description(2, True), "text2")

        # Invalid command
        self.assertEqual(self.protocol.get_command_description(3), "WRONG COMMAND!")
        self.assertEqual(self.protocol.get_command_description(3, True), "WRONG COMMAND!")

        # Protocol not extended
        self.protocol.CLIENT_COMMAND_DESCRIPTION_BY_CODE = None
        self.protocol.SERVER_COMMAND_DESCRIPTION_BY_CODE = None

        self.assertEqual(self.protocol.get_command_description(1), "-")
        self.assertEqual(self.protocol.get_command_description(2, True), "-")
