import inspect
import logging as _logging
import traceback

import os

from napalm.socket.parser import CommandParser
from napalm.socket.server import ServerConfig

logging = _logging.getLogger("PROTOCOL")


# Protocol

class SimpleProtocol:
    is_server_protocol = True
    logging = None

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        """
        Created on connection established.
        :param send_bytes_method: method of server/client to send data.
        :param close_connection_method: method of server/client to disconnect.
        :param address: address of server to listen/connect.
        :param app: additional parameter to get app models and controllers.
        """
        self.send_bytes_method = send_bytes_method
        self.close_connection_method = close_connection_method
        self.address = address
        self.config = config or ServerConfig()

        self.logging = _logging.getLogger("SRV-PROTOCOL" if self.is_server_protocol else "CLN-PROTOCOL")
        self.logging.debug("Protocol created for %s %s", address, self)

        # Protocol instance exists only while connected:
        #  created after connection established and disposed on disconnect for clients,
        #  and on start/stop server respectively for servers.
        if send_bytes_method:
            self.on_connect()

    def dispose(self):
        """
        Always called on disconnect.
        Call protocol.dispose() if you want to disconnect related client.
        :return:
        """
        address = self.address
        self.send_bytes_method = None
        self.address = None
        self.config = None
        if self.close_connection_method:
            self.logging.debug("Protocol disposing... (%s) close_method: %s %s",
                               address, self.close_connection_method, self)
            # Prevent calling protocol.dispose() from close_connection_method
            close_connection_method = self.close_connection_method
            self.close_connection_method = None

            # Disconnect
            try:
                close_connection_method()
            except Exception as error:
                self.logging.error("Error while disconnecting. %s (%s)", error, self.address)

            self.on_disconnect()

            self.logging.debug("Protocol disposed (%s)", address)
        # self.logging = None

    # Send

    def send_raw(self, data):
        """
        Send data as it is, without moving it through parser.
        :param data: str|bytes
        :return:
        """
        if self.send_bytes_method and data:
            # self.logging.debug("Protocol send: %s (%s)", data_bytes, self.address)
            data_bytes = data if isinstance(data, bytes) else data.encode("utf-8")
            self.send_bytes_method(data_bytes)

    def send_all_raw(self, data_list):
        """
        (Here is an optimization: Grouping all data to fit IP frame maximally.)
        :param data_list: iterable of str|bytes
        :return:
        """
        if self.send_bytes_method and data_list:
            buffer = b""
            # -delim_len = len(self.config.DELIMITER)
            for data in data_list:
                data_bytes = data if isinstance(data, bytes) else data.encode("utf-8")
                if len(buffer) + len(data_bytes) > self.config.RECV_SIZE:  # + delim_len
                    # self.logging.debug("Protocol send: %s (%s)", buffer, self.address)
                    self.send_bytes_method(buffer)
                    buffer = data_bytes
                else:
                    buffer += data_bytes  # (self.config.DELIMITER if buffer else b"") +
            if buffer:
                # self.logging.debug("Protocol send: %s (%s)", buffer, self.address)
                self.send_bytes_method(buffer)

    # Process

    def on_connect(self):
        # Override
        pass

    def on_reconnect(self):
        # Override (Only for clients)
        pass

    def on_disconnect(self):
        # Override
        pass

    def process_bytes_list(self, data_bytes_list):
        """
        :param data_bytes_list: iterable of bytes, e.g.
        [b"1||param1||param2##4||param1||param2##", b"5||param1||param2##"]
        :return:
        """
        if data_bytes_list:
            # self.logging.debug("Protocol received: %s (%s)", data_bytes_list, self.address)
            for data_bytes in data_bytes_list:
                self.process_bytes(data_bytes)

    def process_bytes(self, data_bytes):
        # Override
        pass


class Protocol(SimpleProtocol):
    """
    In subclasses override _process_command() to process commands from client
    and add send methods to send commands to client.
    """

    dummy_protocol = None

    parser_class = CommandParser
    parser = None
    player = None

    # (Set plugins here in subclasses to instantiate them in constructor)
    plugins = []

    last_protocol_id = 0

    is_auth_required = False
    authorize_command_to_process = -1

    CLIENT_COMMAND_DESCRIPTION_BY_CODE = None
    SERVER_COMMAND_DESCRIPTION_BY_CODE = None

    # todo remove as its always ready until disposed
    @property
    def is_ready(self):
        return bool(self.send_bytes_method)

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        SimpleProtocol.__init__(self, send_bytes_method, close_connection_method, address, config, app)

        # ID for logging
        Protocol.last_protocol_id += 1
        self.protocol_id = Protocol.last_protocol_id

        # Instances
        if not Protocol.parser:
            parser_class = (self.config.command_parser_class
                            if hasattr(self.config, "command_parser_class") else None
                            ) or self.parser_class
            Protocol.parser = parser_class()
        # self.parser = Protocol.parser
        self.player = None

        self._instantiate_plugins()

        # State
        self.is_send_on_flush = False
        self.deferred_bytes_list = []

    def dispose(self):
        # Send all deferred commands accumulated
        self.flush()

        if self.plugins:
            # (list() needed to make a copy)
            for plugin in list(self.plugins):
                plugin.dispose()
            self.plugins.clear()

        # Also removes player from play and room
        # todo move to gameprotocol?
        if self.player:
            # self.player.detach_protocol()
            self.player.protocol = None
            if hasattr(self.config, "is_continue_on_disconnect")\
                    and self.config.is_continue_on_disconnect:
                # if not Protocol.dummy_protocol:
                #     Protocol.dummy_protocol = self.config.protocol_class()
                self.player.protocol = Protocol.dummy_protocol
        self.parser = None
        self.config = None
        self.player = None

        # ??
        # SimpleProtocol.__init__(self)

    def __repr__(self):
        user_id = self.player.user_id if self.player else "-"
        session_id_suffix = "(" + str(self.player.session_id) + ")" \
            if self.player and self.player.session_id >= 0 else ""
        status = " disconnected" if not self.send_bytes_method else ""
        return "<{0} user_id:{1} address:{2}{3}>".format(
            self.__class__.__name__, user_id + session_id_suffix, self.address, status)

    def _instantiate_plugins(self):
        def process_plugin(plugin):
            # Instantiate if plugin is a class of factory method (both are callable)
            plugin = plugin() if callable(plugin) else plugin
            if plugin and not plugin.protocol:
                plugin.protocol = self
            return plugin

        if self.plugins:
            self.plugins = [process_plugin(plugin) for plugin in self.plugins if plugin]

    # Send

    def set_send_on_flush(self):
        self.is_send_on_flush = True

    def flush(self):
        self.is_send_on_flush = False
        if self.deferred_bytes_list:
            deferred_bytes_list = self.deferred_bytes_list
            self.deferred_bytes_list = []
            self.send_all_raw(deferred_bytes_list)

    def send(self, command):
        """
        :param command: iterable|str
        :return:
        """
        if not self.send_bytes_method:
            return

        # ["1", "param1", "param2"] -> "1||param1||param2##"
        # Or "1||param1||param2" -> "1||param1||param2##"
        command = self.parser.make_command(command)
        # "1||param1||param2" -> b"1||param1||param2##"
        command_bytes = command.encode("utf-8")

        if self.is_send_on_flush:
            self.deferred_bytes_list.append(command_bytes)
            return

        self.send_bytes_method(command_bytes)

    def send_all(self, command_list):
        """
        :param command_list: iterable of iterable|str
        :return:
        """
        if not self.send_bytes_method:
            return

        # [["1", "param1", "param2"], "4||param1||param2"] -> [b"1||param1||param2##", b"4||param1||param2##"]
        command_bytes_list = [self.parser.make_command(command).encode("utf-8")
                              for command in command_list if command]

        if self.is_send_on_flush:
            self.deferred_bytes_list.extend(command_bytes_list)
            return

        self.send_all_raw(command_bytes_list)

    def send_raw(self, data):
        if not self.send_bytes_method:
            return

        if self.is_send_on_flush:
            self.deferred_bytes_list.append(data)
            return

        super().send_raw(data)

    def send_all_raw(self, data_list):
        if not self.send_bytes_method:
            return

        if self.is_send_on_flush:
            self.deferred_bytes_list.extend(data_list)
            return

        super().send_all_raw(data_list)

    # Process

    def on_connect(self):
        # Override
        if self.plugins:
            for plugin in self.plugins:
                plugin.on_connect()

    def on_disconnect(self):
        # Override
        if self.plugins:
            for plugin in self.plugins:
                plugin.on_disconnect()

    def process_bytes_list(self, data_bytes_list):
        # Put to buffer all data sending during processing
        self.set_send_on_flush()
        # Process
        super().process_bytes_list(data_bytes_list)
        # Send buffer
        self.flush()

    def process_bytes(self, data_bytes):
        # b"1||param1||param2##4||param1||param2##" ->
        #  ["1||param1||param2", "4||param1||param2"]
        commands = data_bytes.decode("utf-8")
        command_list = self.parser.split_commands(commands)

        # For each command
        for command in command_list:
            if not command:
                continue

            # Parse
            # "1||param1||param2" -> (1, ["1", "param1", "param2"], 3)
            command_parsed = self._parse_command(command)
            if not command_parsed:
                continue

            # Process
            if command_parsed[0] == self.authorize_command_to_process:
                # Authorize
                self.player = self._process_auth_command(command_parsed[0], command_parsed[1], command_parsed[2])
            elif not self.player and self.is_auth_required:
                # Not authorized but should be
                print(self.protocol_id, "WARNING! (process_auth_command) Command cannot be processed "
                                        "because user is not authorized yet!", "command_params:", command_parsed)
                # todo
                result = "You are not authorized yet! So command cannot be processed: " + str(command_parsed)
                self.send([0, result])
            else:
                # Authorized
                self._process_command(command_parsed[0], command_parsed[1], command_parsed[2])

    def _parse_command(self, command):
        if not command:
            return

        # Policy request
        if "<policy-file-request/>" in command:
            self.send_raw('<?xml version="1.0"?>'
                          '<cross-domain-policy>'
                          '<allow-access-from domain="*" to-ports="*"/>'
                          '</cross-domain-policy>')
            return

        command_params = self.parser.parse_command(command)
        command_code = int(command_params[0]) if command_params[0].isdigit() else command_params[0]
        params_count = len(command_params)

        # Log
        command_description = self.get_command_description(command_code, not self.is_server_protocol)
        print(self.protocol_id, "  parsed command code: %s (%s) params: %s" %
              (command_code, command_description, str(command_params)))

        return command_code, command_params, params_count

    # Override
    # Should return player instance!
    def _process_auth_command(self, command_code, command_params, params_count):
        pass

    # Override
    def _process_command(self, command_code, command_params, params_count):
        # Override
        if self.plugins:
            for plugin in self.plugins:
                plugin.process_command(command_code, command_params, params_count)

    # Utility

    def get_command_description(self, command_code, is_server_command=False):
        description_by_code = self.SERVER_COMMAND_DESCRIPTION_BY_CODE if is_server_command else \
            self.CLIENT_COMMAND_DESCRIPTION_BY_CODE
        return description_by_code[command_code] \
            if description_by_code and command_code in description_by_code \
            else ("WRONG COMMAND!" if description_by_code else "-")


# Experimental
class ProtocolPlugin:
    protocol = None

    def __init__(self, protocol=None):
        self.protocol = protocol

    def dispose(self):
        self.protocol = None

    def on_connect(self):
        # Override
        pass

    def on_disconnect(self):
        # Override
        pass

    def process_command(self, command_code, command_params, params_count):
        # Override
        pass


class ServerProtocol(Protocol):
    is_server_protocol = True


class ClientProtocol(Protocol):
    is_server_protocol = False

    # # Process
    #
    # def on_reconnect(self):
    #     # Override
    #     pass
