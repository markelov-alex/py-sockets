import hashlib

import time

from napalm.play import server_commands, client_commands
from napalm.socket.protocol import Protocol, ServerProtocol


"""
Constants.
 All client constants, such as timing, should be set to client through protocol.
 If we use same constants on server and in client separately, to update them we must 
 update client, which is no good.
"""


# Constants

class CurrencyType:
    CURRENCY_TYPE_HARD = 0
    CURRENCY_TYPE_SOFT = 1


class MessageType:
    # public
    MSG_TYPE_CHAT = 0
    MSG_TYPE_PUBLIC_SPOKEN = 1
    # private
    MSG_TYPE_PRIVATE_SPOKEN = 2
    MSG_TYPE_MAIL = 3

    MSG_DLG_TYPE_OK = 0
    MSG_DLG_TYPE_OK_CANCEL = 1

    @staticmethod
    def is_message_private(message_type):
        return message_type >= MessageType.MSG_TYPE_PRIVATE_SPOKEN


class GameID:
    POKER = 1


class RoomType:
    PUBLIC = 0
    VIP = 1
    PRIVATE = 2


class TournamentType:
    NONE = 0
    SINGLE_ROOM = 1
    MULTI_ROOM_SHOOTOUT = 2
    MULTI_ROOM_SHUFFLE = 3


class FindAndJoin:
    JUST_FIND = 0
    JOIN_ROOM = 1
    JOIN_GAME = 2


class MessageCode:
    # todo move to language.json
    JOIN_ROOM_FAIL_TITLE = "{join_room_fail_title}"
    JOIN_ROOM_FAIL = "{join_room_fail}"
    JOIN_ROOM_FAIL_SAME_USER = "{join_room_fail_same_user}"
    JOIN_ROOM_WRONG_PASSWORD = "{join_room_wrong_password}"

    JOIN_GAME_FAIL_TITLE = "{join_game_fail_title}"
    JOIN_GAME_FAIL = "{join_game_fail}"


# Protocol

# We don't call GameServerProtocol because all modules except client.py is about server.
class GameProtocol(ServerProtocol):
    is_auth_required = True
    authorize_command_to_process = client_commands.AUTHORIZE

    CLIENT_COMMAND_DESCRIPTION_BY_CODE = client_commands.DESCRIPTION_BY_CODE
    SERVER_COMMAND_DESCRIPTION_BY_CODE = server_commands.DESCRIPTION_BY_CODE

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        super().__init__(send_bytes_method, close_connection_method, address, config, app)

        # The entry point for the player to application on connected, but not yet authorized
        self.house = app.house if app else None

    # Called on any disconnect. For reconnected player another new protocol will be given
    def dispose(self):
        # Remove player on disconnect (can be restored on reconnect)
        if self.house and self.player:
            self.house.on_player_disconnected(self.player)
        self.house = None

        super().dispose()

    #
    # def __repr__(self):
    #     session_id_suffix = "(" + str(self.player.session_id) + ")" \
    #           if self.player and self.player.session_id >= 0 else ""
    #     user_id = self.player.user_id if self.player else "-"
    #     return "<GameProtocol user_id:{0} address:{1}{2}>".format(user_id + session_id_suffix, self.address,
    #                                                               " disconnected" if not self.request else "")

    def _process_auth_command(self, command_code, command_params, params_count):
        if not self.house:
            self.logging.error(self.protocol_id +
                               "ERROR! (_process_auth_command) Cannot process auth command without house!"
                               "house: %s", self.house)
            return None
        if self.house.is_paused:
            self.logging.warning("House is paused! Skip.")
            return None

        # Get/create player object
        user_id = command_params[1] if params_count > 1 else ""
        social_id = command_params[2] if params_count > 2 else ""
        access_token = command_params[3] if params_count > 3 else ""
        auth_sig = command_params[4] if params_count > 4 else ""
        backend = command_params[5] if params_count > 5 else ""
        session_id = int(command_params[6]) if params_count > 6 and self.config.is_multiclient_allowed else 0

        # Create access_token for a guest
        is_guest = not bool(social_id)
        if is_guest:
            if not self.config.is_allow_guest_auth:
                self.logging.warning(self.protocol_id + "WARNING! Cannot create model for player "
                                                        "because social_id not defined and guest auth not allowed!"
                                                        "social_id: %s house_config.is_allow_guest_auth: %s", social_id,
                                     self.config.is_allow_guest_auth)
                return None

            md5 = hashlib.md5()
            md5.update(str(time.time()).encode())
            social_id = "guest_" + md5.hexdigest()[0:10]  # str(UserManager.guest_count)
            # UserManager.guest_count += 1

        # (Returns None if auth_sig mismatch)
        player = self.house.on_player_connected(self, user_id, social_id, access_token, auth_sig, backend, session_id)

        if not player:
            self._send_authorize_result(100, "auth error")
            return None

        player.is_guest = is_guest

        self._send_authorize_result(0, player.export_public_data())

        # self.house.check_restore_player(player)
        self._on_auth(player)
        return player

    def _on_auth(self, player):
        # moved to on_player_connected()
        # -player.update_self_user_info()

        # todo To avoid showing lobby without user info, check user's info updated from backend
        # (see on_player_connected()), otherwise wait until updated before calling goto_lobby()
        self.house.goto_lobby(player)

    def _process_command(self, command_code, command_params, params_count):
        if not self.house or not self.player:
            self.logging.error(self.protocol_id +
                               "ERROR! (process_command) Cannot process command while main objects are not created!"
                               "house: %s player: %s", self.house, self.player)
            return

        self.logging.debug(self.protocol_id + "info (_process_command) command_code: %s"
                                              "command_params: %s params_count: %s", command_code, command_params,
                           params_count)
        if self.house.is_paused:
            self.logging.warning("House is paused! Skip.")
            return None

        # Lobby
        if command_code == client_commands.UPDATE_SELF_USER_INFO:
            self.player.update_self_user_info()
        elif command_code == client_commands.GET_LOBBY_INFO_LIST:
            self.player.house.get_lobby_info_list(self.player)
        elif command_code == client_commands.CHANGE_LOBBY:
            # Client should reconnect to another server by himself
            lobby_id = None if params_count <= 1 else int(command_params[1])
            self.player.house.goto_lobby(self.player, lobby_id)
        elif command_code == client_commands.GET_ROOMS_LIST:
            # todo?-
            # room_code = "" if params_count <= 1 else command_params[1]
            # game_id, game_variation, game_type, room_type = self.parser.parse_room_code(room_code)

            self.player.lobby.get_room_list(self.player)  # , game_id, game_type, room_type)
        elif command_code == client_commands.FIND_FREE_ROOM:
            find_and_join = FindAndJoin.JOIN_ROOM if params_count <= 1 else int(command_params[1])
            room_code = "" if params_count <= 2 else command_params[2]
            # todo add in client
            max_stake = 0 if params_count <= 3 else float(command_params[3])

            # room_code="1_H_10_0" | "1___0" | "1_H_10_0" | "1_H_" |  "1" | ...
            game_id, game_variation, game_type, room_type = self.parser.parse_room_code(room_code)

            self.player.lobby.find_free_room(self.player, find_and_join, game_id, game_variation, game_type, room_type, max_stake)
        elif command_code == client_commands.GET_ROOM_INFO:
            if params_count > 1:
                room_id = command_params[1]
                self.player.lobby.get_room_info(self.player, room_id)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. command_params: %s",
                                     command_params)
        elif command_code == client_commands.CREATE_ROOM:
            if params_count > 1:
                room_info = command_params[1]
                self.player.lobby.create_room(self.player, room_info)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. command_params: %s",
                                     command_params)
        elif command_code == client_commands.EDIT_ROOM:
            if params_count > 2:
                room_id = command_params[1]
                room_info = command_params[2]
                self.player.lobby.edit_room(self.player, room_id, room_info)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. command_params: %s",
                                     command_params)
        elif command_code == client_commands.DELETE_ROOM:
            if params_count > 2:
                room_id = command_params[1]
                self.player.lobby.delete_room(self.player, room_id)

        # Room
        elif command_code == client_commands.GET_GAME_INFO:
            if params_count > 1:
                room_id = command_params[1]
                is_get_room_content = 0 if params_count <= 2 else int(command_params[2])
                self.player.lobby.get_game_info(self.player, room_id, is_get_room_content)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. "
                                                        "command_params: %s player: %s",
                                     command_params, self.player)
        elif command_code == client_commands.GET_PLAYER_INFO:
            if params_count > 1:
                place_index = int(command_params[1])
                room_id = "" if params_count <= 2 else command_params[2]
                if self.player.game:
                    self.player.game.get_player_info(self.player, place_index)
                elif room_id:
                    self.player.lobby.get_player_info_in_game(self.player, room_id, place_index)
                else:
                    self.logging.warning(self.protocol_id + "WARNING! (process_command) Cannot get player info."
                                                            "player.play: %s room_id: %s command_params: %s player: %s",
                                         self.player.game, room_id, command_params, self.player)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. "
                                                        "command_params: %s player: %s", command_params, self.player)
        elif command_code == client_commands.JOIN_THE_ROOM:
            if params_count > 1:
                room_id = command_params[1]
                password = None if params_count <= 2 else command_params[2]
                self.player.lobby.join_the_room(self.player, room_id, password)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. "
                                                        "command_params: %s player: %s", command_params, self.player)
        elif command_code == client_commands.JOIN_THE_GAME:
            room_id = "" if params_count <= 1 else command_params[1]
            password = None if params_count <= 2 else command_params[2]
            place_index = -1 if params_count <= 3 else int(command_params[3])
            money_in_play = 0 if params_count <= 4 else float(command_params[4])
            self.player.lobby.join_the_game(self.player, room_id, password, place_index, money_in_play)
        elif command_code == client_commands.LEAVE_THE_GAME:
            self.player.lobby.leave_the_game(self.player)
        elif command_code == client_commands.LEAVE_THE_ROOM:
            self.player.lobby.leave_the_room(self.player)
        elif command_code == client_commands.INVITE_FRIENDS_TO_ROOM:
            pass  # todo
        elif command_code == client_commands.SEND_MESSAGE:
            if params_count > 2:
                message_type = int(command_params[1])
                text = command_params[2]
                receiver_id = command_params[3] if params_count > 3 else -1

                # (Protocol -> House -> Room|Lobby -> player.protocol)
                self.player.house.send_message(message_type, text, self.player, receiver_id, True)
            else:
                self.logging.warning(self.protocol_id + "WARNING! (process_command) Wrong params. "
                                                        "command_params: %s player: %s", command_params, self.player)

        # Game
        elif command_code == client_commands.READY_TO_START:
            is_ready = int(command_params[1]) if params_count > 1 else True
            if self.player.game:
                self.player.game.ready_to_start(self.player, is_ready)
            else:
                self.logging.warning(self.protocol_id +
                                     "WARNING! (process_command) Player is not in play. "
                                     "command_params: %s game: %s player: %s",
                                     command_params, self.player.game, self.player)
        elif command_code == client_commands.ACTION1:
            if params_count > 1 and self.player.game:
                self.player.game.action1(command_params[1:])
            else:
                self.logging.warning(self.protocol_id +
                                     "WARNING! (process_command) Player is not in play or wrong params. "
                                     "command_params: %s play: %s player: %s", command_params, self.player.game,
                                     self.player)
        elif command_code == client_commands.ACTION2:
            if params_count > 1 and self.player.game:
                self.player.game.action2(command_params[1:])
            else:
                self.logging.warning(self.protocol_id +
                                     "WARNING! (process_command) Player is not in play or wrong params.",
                                     "command_params: %s play: %s player: %s", command_params, self.player.game,
                                     self.player)
        elif command_code == client_commands.RAW_BINARY_ACTION:
            if params_count > 1 and self.player.game:
                raw_binary = command_params[1]
                self.player.game.process_raw_binary_action(raw_binary)
            else:
                self.logging.warning(self.protocol_id +
                                     "WARNING! (process_command) Player is not in play or wrong params.",
                                     "command_params: %s play: %s player: %s", command_params, self.player.game,
                                     self.player)

        # Default
        # else:
        #     self.logging.warning(self.protocol_id, "WARNING! (process_command) Unknown command!", "command_params:", command_params,
        #           "player:", self.player)
        #     # demo
        #     result = "[Unknown command: " + str(command_params) + "]"
        #     # parser.PARAMS_DELIM.join(command_params).upper()
        #     self.send([result])

        super()._parse_command(command_code, command_params, params_count)

    def _send_authorize_result(self, code, body):
        self.send([server_commands.AUTHORIZE_RESULT, code, body])

    # Lobby

    # todo implement lobby_info on server and flash client
    def goto_lobby(self, lobby_info):
        self.send([server_commands.GOTO_LOBBY, lobby_info])

    def lobby_info_list(self, house_id, lobby_info_list):
        self.send([server_commands.LOBBY_INFO_LIST, house_id, lobby_info_list])

    def rooms_list(self, room_info_list):
        self.send([server_commands.ROOMS_LIST, room_info_list])

    def room_info(self, room_info, player_info_list=None):
        """
        :param room_info:
        :param player_info_list: all players in the room: visitors and players by the table.
        Usually, not used, because most clients don't display visitors
        :return:
        """
        self.send([server_commands.ROOM_INFO, room_info or self.parser.EMPTY, player_info_list or self.parser.EMPTY])

    def game_info(self, game_info, player_info_list=None):
        self.send([server_commands.GAME_INFO, game_info or self.parser.EMPTY, player_info_list or self.parser.EMPTY])

    def player_info(self, place_index, player_info):
        self.send([server_commands.PLAYER_INFO, place_index, player_info or self.parser.EMPTY])

    # Room

    # todo update_self_player_info?
    def update_self_user_info(self, self_user_info):
        # todo? update info from php server?
        self.send([server_commands.UPDATE_SELF_USER_INFO, self_user_info])

    def confirm_joined_the_room(self, room_info):
        self.send([server_commands.CONFIRM_JOINED_THE_ROOM, room_info])

    def player_joined_the_room(self, player_info):
        self.send([server_commands.PLAYER_JOINED_THE_ROOM, player_info])

    def player_joined_the_game(self, place_index, player_info):  # , log_text
        self.send([server_commands.PLAYER_JOINED_THE_GAME, place_index, player_info])  # , log_text

    def player_left_the_game(self, place_index):
        self.send([server_commands.PLAYER_LEFT_THE_GAME, place_index])

    def confirm_left_the_room(self):
        self.send([server_commands.CONFIRM_LEFT_THE_ROOM])

    def player_left_the_room(self, user_id):
        self.send([server_commands.PLAYER_LEFT_THE_ROOM, user_id])

    def send_message(self, message_type, text, sender, receiver_id=-1):
        """
        :param message_type:
        :param text:
        :param sender: Player|User
        :param receiver_id:
        :return:
        """
        sender_id = sender.user_id
        color_index = 0
        command_params = [server_commands.MESSAGE, message_type, text, sender_id, color_index]

        if receiver_id >= 0:
            is_message_private = MessageType.is_message_private(message_type)
            if is_message_private and self.player.user_id != receiver_id:
                self.logging.warning(self.protocol_id + "WARNING! (player.send_message) "
                                                        "Trying to send private message to wrong receiver! "
                                                        "receiver_id: %s try to send to player: %s command_params: %s",
                                     receiver_id, self, command_params)
                return
            command_params.append(receiver_id)

        self.send(command_params)

    def show_ok_message_dialog(self, title, text):
        self._show_message_dialog(MessageType.MSG_DLG_TYPE_OK, title, text)

    def show_ok_cancel_message_dialog(self, title, text):
        self._show_message_dialog(MessageType.MSG_DLG_TYPE_OK_CANCEL, title, text)

    def _show_message_dialog(self, dialog_type, title, text):
        self.send([server_commands.SHOW_MESSAGE_DIALOG, dialog_type, title, text])

    def send_log(self, log_text):
        self.send([server_commands.LOG, log_text])

    def ready_to_start(self, place_index, is_ready, start_game_countdown_sec):
        self.send([server_commands.READY_TO_START, place_index, int(is_ready), start_game_countdown_sec])

    def reset_game(self):
        self.send([server_commands.RESET_GAME])

    def change_player_turn(self, place_index, turn_timeout_sec):
        self.send([server_commands.CHANGE_PLAYER_TURN, place_index, turn_timeout_sec])

    # ???- place_index
    def show_cashbox_dialog(self):  # , place_index
        self.send([server_commands.SHOW_CASHBOX_DIALOG])  # , place_index])

    def player_wins(self, place_index, money_win, player_money_in_play):
        self.send([server_commands.PLAYER_WINS, place_index, money_win, player_money_in_play])

    def player_wins_the_tournament(self, place_index, money_win):
        self.send([server_commands.PLAYER_WINS_THE_TOURNAMENT, place_index, money_win])

    def update1(self, *args):
        self.send([server_commands.UPDATE1] + args)

    def update2(self, *args):
        self.send([server_commands.UPDATE2] + args)

    def raw_binary_update(self, raw_binary):
        self.send([server_commands.RAW_BINARY_UPDATE, raw_binary])
