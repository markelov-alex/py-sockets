import traceback

from napalm.socket.parser import CommandParser
from napalm.socket.server import ServerConfig

"""
todo!
1. move all command sending to XxxProtocol classes
2. extract play classes to another module
3. in Game, Room, Lobby and others methods that send or broadcast send commands
        through Protocol's methods must begin with "send_"

todo group sending messages for all players!
"""


# Protocol

class Protocol:
    """
    In subclasses override _process_command() to process commands from client
    and add send methods to send commands to client.
    """
    dummy_protocol = None

    parser_class = CommandParser
    parser = None

    last_protocol_id = 0

    CLIENT_COMMAND_DESCRIPTION_BY_CODE = None
    SERVER_COMMAND_DESCRIPTION_BY_CODE = None
    authorize_client_command = -1

    @property
    def is_ready(self):
        return bool(self.send_bytes_method)

    def __init__(self, send_bytes_method=None, close_connection_method=None, app=None, address=None):
        # if not Protocol.dummy_protocol:
        #     Protocol.dummy_protocol = self.__class__()

        # ID for logging
        Protocol.last_protocol_id += 1
        self.protocol_id = Protocol.last_protocol_id

        # Params
        self.send_bytes_method = send_bytes_method
        self.close_connection_method = close_connection_method
        self.server_config = app.lobby_model if app else ServerConfig()
        self.address = address

        # Instances
        if not Protocol.parser:
            parser_class = (self.server_config.command_parser_class
                            if hasattr(self.server_config, "command_parser_class") else None) or self.parser_class
            Protocol.parser = parser_class()
        # self.parser = Protocol.parser
        self.player = None

        # State
        self.is_send_on_flush = False
        self.deferred_command_params_list = []

    def dispose(self):
        # Send all deferred commands accumulated
        self.flush()

        # Also removes player from play and room
        if self.player:
            # self.player.detach_protocol()
            self.player.protocol = None
            if self.server_config.continue_game_on_user_reconnect:
                # if not Protocol.dummy_protocol:
                #     Protocol.dummy_protocol = self.server_config.protocol_class()
                self.player.protocol = Protocol.dummy_protocol
        self.player = None

        if self.close_connection_method:
            print(self.protocol_id, "CLOSE connection;", self.address)
            self.close_connection_method()
        self.send_bytes_method = None
        self.close_connection_method = None
        self.server_config = None
        self.address = None

        self.parser = None

    def __repr__(self):
        session_id_suffix = "(" + str(
            self.player.session_id) + ")" if self.player and self.player.session_id >= 0 else ""
        user_id = self.player.user_id if self.player else "-"
        return "<{0} user_id:{1} address:{2}{3}>".format(
            self.__class__.__name__, user_id + session_id_suffix,
            self.address, " disconnected" if not self.send_bytes_method else "")

    # Send

    def send_on_flush(self):
        # print(self.protocol_id, "(send_on_flush) prev-is_send_on_flush", self.is_send_on_flush)
        # traceback.print_stack()
        self.is_send_on_flush = True
        # print(self.protocol_id, " (send_on_flush) is_send_on_flush", self.is_send_on_flush)

    def sendall(self, command_params_list):
        if not self.send_bytes_method:
            print(self.protocol_id, " > temp (sendall) Sending failed. Possibly player is (temporarily) disconnected.",
                  "send_bytes_method:", self.send_bytes_method, "command_params_list:", command_params_list)
            return

        if self.is_send_on_flush:
            print(self.protocol_id, " > temp (sendall) append to deferred:", command_params_list)
            self.deferred_command_params_list.extend(command_params_list)
            return

        # [["1", "param1", "param2"], ["4", "param1", "param2"]] -> ["1||param1||param2", "4||param1||param2"]
        command_data_list = [self.parser.make_command(command_params) for command_params in command_params_list]
        # ["1||param1||param2", "4||param1||param2"] -> "1||param1||param2##4||param1||param2"
        commands_data = self.parser.join_commands(command_data_list)
        # "1||param1||param2##4||param1||param2" -> b"1||param1||param2##4||param1||param2"
        commands_data_bytes = commands_data.encode("utf-8")

        # Print
        description_by_code = self.SERVER_COMMAND_DESCRIPTION_BY_CODE
        for command_params in command_params_list:
            command_code = command_params[0]
            print(self.protocol_id, "  >>> send command: %s (%s) params: %s" %
                  (command_code, description_by_code[command_code]
                      if description_by_code and command_code in description_by_code
                      else ("WRONG COMMAND!" if description_by_code else "-"), str(command_params)))

        print(self.protocol_id, "    >>> SEND:", commands_data_bytes, "length:", len(commands_data_bytes), self)
        self.send_bytes_method(commands_data_bytes)

    def send(self, command_params: list):
        if not self.send_bytes_method:
            print(self.protocol_id, " > temp (send) Sending failed. Possibly player is (temporarily) disconnected. "
                                    "send_bytes_method:", self.send_bytes_method, "command_params:", command_params)
            return

        if self.is_send_on_flush:
            print(self.protocol_id, " > temp (send) append to deferred command_params:", command_params,
                  self._get_command_description(command_params[0], True))  # , "is_send_on_flush:", self.is_send_on_flush)
            self.deferred_command_params_list.append(command_params)
            return

        # ["1", "param1", "param2"] -> "1||param1||param2"
        command_data = self.parser.make_command(command_params)
        # "1||param1||param2" -> b"1||param1||param2"
        command_data_bytes = command_data.encode("utf-8")

        # print(self.protocol_id, "    send to client bytes:", command_data_bytes)
        # Print
        command_code = command_params[0]
        print(self.protocol_id, "  >>> send command: %s (%s) params: %s" %
              (command_code, self._get_command_description(command_code, True), str(command_params)))

        self.send_bytes_method(command_data_bytes)

    def send_raw(self, data):
        if not self.send_bytes_method:
            print(self.protocol_id, " > temp (send_raw) Sending failed. Possibly player is (temporarily) disconnected. "
                                    "send_bytes_method:", self.send_bytes_method, "data:", data)
            return

        data_bytes = data if isinstance(data, bytes) else data.encode("utf-8")
        print(self.protocol_id, "  >>>    send to client bytes:", data_bytes)
        self.send_bytes_method(data_bytes)

    def flush(self):
        # print(self.protocol_id, "(flush) prev-is_send_on_flush:", self.is_send_on_flush,
        #       "len(deferred_command_params_list):", len(self.deferred_command_params_list))
        self.is_send_on_flush = False
        if self.deferred_command_params_list:
            command_params_list = self.deferred_command_params_list[:]
            self.deferred_command_params_list = []
            # print(self.protocol_id, "temp FLUSH", command_params_list)
            self.sendall(command_params_list)
        # print(self.protocol_id, " (flush) is_send_on_flush:", self.is_send_on_flush,
        #       "len(deferred_command_params_list):", len(self.deferred_command_params_list))

    # Parse and process

    def process_commands(self, commands_data_list):
        # Put all commands to buffer
        self.send_on_flush()

        # print(self.protocol_id, "temp (process_commands)", commands_data_list)
        for commands_data in commands_data_list:
            # "1||param1||param2##4||param1||param2##" -> ["1||param1||param2", "4||param1||param2"]
            commands_data = commands_data.decode()
            command_list = self.parser.split_commands(commands_data)

            # For each command
            for command in command_list:
                if not command:
                    continue

                # Parse
                command_parsed = self._parse_command(command)
                if not command_parsed:
                    continue

                # Process
                if command_parsed[0] == self.authorize_client_command:
                    # Authorize
                    self.player = self._process_auth_command(command_parsed[0], command_parsed[1], command_parsed[2])
                elif not self.player:
                    # Not authorized
                    print(self.protocol_id, "WARNING! (process_auth_command) Command cannot be processed "
                          "because user is not authorized yet!", "command_params:", command_parsed)
                    # todo
                    result = "You are not authorized yet! So command cannot be processed: " + str(command_parsed)
                    self.send([0, result])
                else:
                    # Authorized
                    self._process_command(command_parsed[0], command_parsed[1], command_parsed[2])

        # Send buffer to client
        self.flush()

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
        command_code = int(command_params[0])
        params_count = len(command_params)

        print(self.protocol_id, "  parsed command code: %s (%s) params: %s" %
              (command_code, self._get_command_description(command_code), str(command_params)))
        return command_code, command_params, params_count

    # Override
    # Should return player instance!
    def _process_auth_command(self, command_code, command_params, params_count):
        pass

    # Override
    def _process_command(self, command_code, command_params, params_count):
        pass

    # Utility

    def _get_command_description(self, command_code, is_server_command=False):
        description_by_code = self.SERVER_COMMAND_DESCRIPTION_BY_CODE if is_server_command else \
            self.CLIENT_COMMAND_DESCRIPTION_BY_CODE
        return description_by_code[command_code] \
            if description_by_code and command_code in description_by_code \
            else ("WRONG COMMAND!" if description_by_code else "-")
