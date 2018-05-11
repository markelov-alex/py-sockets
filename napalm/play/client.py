import logging as _logging

from napalm.async import ThreadedTimer
from napalm.core import ReloadableModel
from napalm.play import server_commands, client_commands
from napalm.play.game import GameConfigModel, Game
from napalm.play.house import HouseModel, Player
from napalm.play.lobby import RoomModel, LobbyModel
from napalm.play.protocol import MessageType, FindAndJoin
from napalm.socket.client import ClientConfig
from napalm.socket.parser import CommandParser
from napalm.socket.protocol import ClientProtocol
from napalm.utils import object_util


class GameClientConfig(ClientConfig):
    timer_class = ThreadedTimer
    house_model_class = HouseModel
    lobby_model_class = LobbyModel
    room_model_class = RoomModel
    game_config_model_class = GameConfigModel


# Player

class ClientPlayer(ReloadableModel):

    user_id = None
    social_id = None
    first_name = None
    last_name = None
    image_url = None
    image_url_small = None
    image_url_normal = None
    level = None
    money_amount = None
    total_money_amount = None
    # is_in_game = None
    join_date = None
    vip_days_available = None

    @property
    def is_self(self):
        # Is current client's player model. False - for enemies
        return bool(self.protocol)

    @property
    def is_in_lobby(self):
        return not bool(self.room)

    @property
    def is_in_room(self):
        return bool(self.room)

    @property
    def is_in_game(self):
        return bool(self.game)

    __public_property_names = Player()._public_property_names

    @property
    def _public_property_names(self):
        return self.__public_property_names

    def __init__(self, info, protocol=None):
        super().__init__()
        self.logging = _logging.getLogger("CL-PLAYER")
        self.protocol = protocol
        self.import_public_data(info)

        self.house = None
        # Not None always (if joined the lobby or room)
        self.lobby = None
        # Not None if joined the room
        self.room = None
        # Not None if joined the game
        self.game = None


class ClientGameModel(ReloadableModel):

    room_id = None
    player_in_turn_index = None
    prev_player_in_turn_index = None
    round_index = None

    _is_in_progress = None

    @property
    def is_in_progress(self):
        return self._is_in_progress

    __public_property_names = Game(None)._public_property_names

    @property
    def _public_property_names(self):
        return self.__public_property_names

    _player_by_place_index_list = None

    @property
    def player_by_place_index_list(self):
        return self._player_by_place_index_list

    @player_by_place_index_list.setter
    def player_by_place_index_list(self, value):
        """
        Note: any item of this cannot refer to client's player instance.
        Check is self by comparing user_id property.
        :param value:
        :return:
        """
        # if not value:
        #     self._player_by_place_index_list = []
        #     return
        #
        # if not self._player_by_place_index_list:
        #     self._player_by_place_index_list = []
        #
        # new_models = [ClientPlayer(info) for info in value] if value else []
        #
        # len_new = len(value)
        # len_current = len(self._player_by_place_index_list)
        # if len_current < len_new:
        #     self._player_by_place_index_list.extend([None] * (len_new - len_current))
        # for i in range(max(len_new, len_current)):
        #     new_info = value[i] if i < len_new else None
        #     new_model = new_models[i] if i < len_new else None
        #     current_player = self._player_by_place_index_list[i]
        #     if not new_model or not current_player or new_model.user_id != current_player.user_id:
        #         self._player_by_place_index_list[i] = new_model
        #     else:
        #         current_player.import_public_data(new_info)

        self._player_by_place_index_list = [ClientPlayer(info) for info in value] if value else []

    def __init__(self, room_model):
        super().__init__()
        self.room_model = room_model
        self.logging = _logging.getLogger("CL-GAME")

        # self.player_by_place_index_list = []

        self.round_index = -1
        self.player_in_turn_index = -1
        self.prev_player_in_turn_index = -1

    def update_place(self, place_index, player_info):
        players_len = len(self._player_by_place_index_list)
        add_count = place_index - players_len + 1
        if add_count > 0:
            self._player_by_place_index_list.extend([None] * add_count)

        player = ClientPlayer(player_info) if player_info else None
        self._player_by_place_index_list[place_index] = player
        return player


class ClientRoomModel(ReloadableModel):

    room_id = None
    room_name = None

    # room_code = None
    game_id = None
    game_variation = None
    game_type = None
    room_type = None

    # game_params = None
    min_stake = None
    max_stake = None

    max_player_count = None
    max_visitor_count = None
    is_password_needed = None
    playing_count = None
    visitor_count = None
    # Timers
    turn_timeout_sec = None
    between_rounds_delay_sec = None

    __public_property_names = RoomModel()._public_property_names

    @property
    def _public_property_names(self):
        return self.__public_property_names

    __game_property_name_list = RoomModel()._game_property_name_list

    @property
    def _game_property_name_list(self):
        return self.__game_property_name_list

    _room_code = None

    @property
    def room_code(self):
        return self._room_code

    @room_code.setter
    def room_code(self, value):
        self._room_code = value
        # Parse room_code
        self.game_id, self.game_variation, self.game_type, self.room_type = CommandParser.parse_room_code(self._room_code)

    _game_params = None

    @property
    def game_params(self):
        return self._game_params

    @game_params.setter
    def game_params(self, value):
        self._game_params = value
        object_util.set_up_object(self, self._game_params, self._game_property_name_list)

    _player_list = None

    @property
    def player_list(self):
        return self._player_list

    @player_list.setter
    def player_list(self, value):
        self._player_list = [ClientPlayer(info) if not isinstance(info, ClientPlayer) else info
                             for info in value] if value else []

    def __init__(self, info):
        super().__init__()
        # self.logging = _logging.getLogger("CL-ROOM")

        self.players = []

        self.import_public_data(info)

    def update_or_create_game(self, game_info):
        if not self.game:
            self.game = ClientGameModel(game_info)
            self.game.room = self
        else:
            self.game.import_public_data(game_info)


class ClientLobbyModel(ReloadableModel):

    lobby_id = None
    lobby_name = None
    # rooms = None

    __public_property_names = LobbyModel()._public_property_names

    @property
    def _public_property_names(self):
        return self.__public_property_names

    _rooms = None

    @property
    def rooms(self):
        return self._rooms

    @rooms.setter
    def rooms(self, value):
        self._rooms = [ClientRoomModel(info) for info in value] if value else []

    def __init__(self, info):
        super().__init__()
        # self.logging = _logging.getLogger("CL-LOBBY")

        self.import_public_data(info)

    # def import_public_data(self, data_list):
    #     super().import_public_data(data_list)
    #
    #     self.rooms = [ClientRoomModel(room_info) for room_info in self.rooms]


class ClientHouseModel(ReloadableModel):

    house_id = None
    house_name = None
    host = None
    port = None
    players_online = None

    __public_property_names = HouseModel()._public_property_names

    @property
    def _public_property_names(self):
        return self.__public_property_names

    _lobbies = None

    @property
    def lobbies(self):
        return self._lobbies

    @lobbies.setter
    def lobbies(self, value):
        self._lobbies = [ClientLobbyModel(info) for info in value] if value else []

    def __init__(self, info):
        super().__init__()
        # self.logging = _logging.getLogger("CL-HOUSE")

        # self.lobbies = []

        self.import_public_data(info)


# Protocol

class GameClientProtocol(ClientProtocol):
    is_auth_required = True
    authorize_command_to_process = server_commands.AUTHORIZE_RESULT

    CLIENT_COMMAND_DESCRIPTION_BY_CODE = client_commands.DESCRIPTION_BY_CODE
    SERVER_COMMAND_DESCRIPTION_BY_CODE = server_commands.DESCRIPTION_BY_CODE

    def __init__(self, send_bytes_method=None, close_connection_method=None, address=None, config=None, app=None):
        super().__init__(send_bytes_method, close_connection_method, address, config, app)

        self.credentials = app

    # Called on any disconnect. For reconnected player another new protocol will be given
    def dispose(self):
        self.credentials = None

        super().dispose()

    # def __repr__(self):
    #     session_id_suffix = "(" + str(self.player.session_id) + ")" \
    #           if self.player and self.player.session_id >= 0 else ""
    #     user_id = self.player.user_id if self.player else "-"
    #     return "<GameProtocol user_id:{0} address:{1}{2}>".format(user_id + session_id_suffix, self.address,
    #                                                               " disconnected" if not self.request else "")

    def on_connect(self):
        super().on_connect()
        self.auth()

    # Receive

    def _process_auth_command(self, command_code, command_params, params_count):
        # Get/create player object
        code = int(command_params[1])
        body = player_info = command_params[2] if params_count > 2 else ""

        if code > 0:
            self.logging.error("Error while authorizing! code: %s, body: %", code, body)
            return None

        player = ClientPlayer(player_info, self)
        return player

    def _process_command(self, command_code, command_params, params_count):
        if not self.player:
            self.logging.error(self.protocol_id +
                               "ERROR! (process_command) Cannot process command while main objects are not created!"
                               "player: %s", self.player)
            return

        self.logging.debug(self.protocol_id + "info (_process_command) command_code: %s"
                                              "command_params: %s params_count: %s", command_code, command_params,
                           params_count)

        # Lobby
        if command_code == server_commands.GOTO_LOBBY:
            lobby_info = command_params[1]
            self.player.lobby = ClientLobbyModel(lobby_info)

            self.on_goto_lobby(self.player.lobby)
        elif command_code == server_commands.LOBBY_INFO_LIST:
            house_id = command_params[1]
            lobby_info_list = command_params[2]
            # Supposed, that lobby_info_list received only for current house
            if not self.player.house or self.player.house.house_id != house_id:
                self.player.house = ClientHouseModel([house_id])
            self.player.house.lobbies = lobby_info_list

            self.on_lobby_info_list(house_id, self.player.house.lobbies)
        elif command_code == server_commands.ROOMS_LIST:
            room_info_list = command_params[1]
            if self.player.lobby:
                self.player.lobby.rooms = room_info_list

            self.on_rooms_list(self.player.lobby.rooms)
        elif command_code == server_commands.ROOM_INFO:
            room_info = command_params[1]
            player_info_list = command_params[2] if params_count > 2 else None
            # Only update, creating only on joining the room
            if self.player.room:
                self.player.room.import_public_data(room_info)
                self.player.room.player_list = player_info_list

            self.on_room_info(self.player.room or ClientRoomModel(room_info))
        elif command_code == server_commands.GAME_INFO:
            game_info = command_params[1]
            player_info_list = command_params[2] if params_count > 2 else None
            self.player.room.update_or_create_game(game_info)
            self.player.room.game.player_by_place_index_list = player_info_list

            self.on_game_info(self.player.room.game, self.player.room.game.player_by_place_index_list)
        elif command_code == server_commands.PLAYER_INFO:
            place_index = int(command_params[1])
            player_info = command_params[2]
            player = self.player.room.game.update_place(place_index, player_info)

            self.on_player_info(place_index, player)

        # Room
        elif command_code == server_commands.UPDATE_SELF_USER_INFO:
            self_user_info = command_params[1]
            # todo check that it's player_info, not user_info, or fix
            self.player.import_public_data(self_user_info)

            self.on_update_self_user_info()
        elif command_code == server_commands.CONFIRM_JOINED_THE_ROOM:
            room_info = command_params[1]
            self.player.room = ClientRoomModel(room_info)

            self.on_confirm_joined_the_room(self.player.room)
        elif command_code == server_commands.PLAYER_JOINED_THE_ROOM:
            player_info = command_params[1]
            player = ClientPlayer(player_info)
            self.player.room.players.append(player)

            self.on_player_joined_the_room(player)
        elif command_code == server_commands.PLAYER_JOINED_THE_GAME:
            place_index = int(command_params[1])
            player_info = command_params[2]
            player = self.player.room.game.update_place(place_index, player_info)
            if player.user_id == self.player.user_id:
                self.player.place_index = place_index
                self.player.game = self.player.room.game

            self.on_player_joined_the_game(place_index, player)
        elif command_code == server_commands.PLAYER_LEFT_THE_GAME:
            place_index = int(command_params[1])
            player = self.player.game.update_place(place_index, None)
            if self.player.place_index == place_index:
                self.player.place_index = -1
                self.player.game = None

            self.on_player_left_the_game(place_index, player)
        elif command_code == server_commands.CONFIRM_LEFT_THE_ROOM:
            # Dispose room and game
            self.player.room = None
            self.player.game = None

            self.on_confirm_left_the_room()
        elif command_code == server_commands.PLAYER_LEFT_THE_ROOM:
            user_id = command_params[1]
            player = next([player for player in self.player.room.players if player.user_id == user_id])
            self.player.room.players.remove(player)

            self.on_player_left_the_room(user_id, player)
        elif command_code == server_commands.MESSAGE:
            message_type = int(command_params[1])
            text = command_params[2]
            sender_id = command_params[3]
            color_index = int(command_params[4])
            receiver_id = command_params[5] if params_count > 5 else None
            # todo?

            self.on_message(message_type, text, sender_id, color_index, receiver_id)
        elif command_code == server_commands.SHOW_MESSAGE_DIALOG:
            dialog_type = int(command_params[1])
            title = command_params[2]
            text = command_params[3]
            # todo?

            self.on_show_message_dialog(dialog_type, title, text)
            if dialog_type == MessageType.MSG_DLG_TYPE_OK:
                self.on_show_ok_message_dialog(title, text)
            elif dialog_type == MessageType.MSG_DLG_TYPE_OK:
                self.on_show_ok_cancel_message_dialog(title, text)
        elif command_code == server_commands.LOG:
            log_text = command_params[1]
            self.on_log(log_text)

        # Game
        elif command_code == server_commands.READY_TO_START:
            place_index = int(command_params[1])
            is_ready = int(command_params[2])
            start_game_countdown_sec = int(command_params[3])
            self.on_ready_to_start(place_index, is_ready, start_game_countdown_sec)
        elif command_code == server_commands.RESET_GAME:
            self.on_reset_game()
        elif command_code == server_commands.CHANGE_PLAYER_TURN:
            place_index = int(command_params[1])
            turn_timeout_sec = int(command_params[2])
            player = self.player.room.game.player_by_place_index_list[place_index]

            self.on_change_player_turn(place_index, player, turn_timeout_sec)
        elif command_code == server_commands.SHOW_CASHBOX_DIALOG:
            # place_index = int(command_params[1])
            self.on_show_cashbox_dialog()
        elif command_code == server_commands.PLAYER_WINS:
            place_index = int(command_params[1])
            money_win = float(command_params[2])
            player_money_in_play = float(command_params[3])
            if self.player.place_index == place_index:
                self.player.money_in_play = player_money_in_play
            player = self.player.room.game.player_by_place_index_list[place_index]
            player.money_in_play = player_money_in_play

            self.on_player_wins(place_index, player, money_win, player_money_in_play)
        elif command_code == server_commands.PLAYER_WINS_THE_TOURNAMENT:
            place_index = int(command_params[1])
            money_win = float(command_params[2])
            player = self.player.room.game.player_by_place_index_list[place_index]

            self.on_player_wins_the_tournament(place_index, player, money_win)
        elif command_code == server_commands.UPDATE1:
            args = command_params[1:]
            self.on_update1(*args)
        elif command_code == server_commands.UPDATE2:
            args = command_params[1:]
            self.on_update2(*args)
        elif command_code == server_commands.RAW_BINARY_UPDATE:
            raw_binary = command_params[1]
            self.on_raw_binary_update(raw_binary)

        super()._parse_command(command_code, command_params, params_count)

    # Override to call AI

    # Lobby

    def on_goto_lobby(self, lobby):
        pass

    def on_lobby_info_list(self, house_id, lobby_list):
        pass

    def on_rooms_list(self, room_list):
        pass

    def on_room_info(self, room):
        pass

    def on_game_info(self, game, player_by_place_index_list):
        pass

    def on_player_info(self, place_index, player):
        pass

    # Room

    def on_update_self_user_info(self):
        pass

    def on_confirm_joined_the_room(self, room):
        pass

    def on_player_joined_the_room(self, player):
        pass

    def on_player_joined_the_game(self, place_index, player):
        pass

    def on_player_left_the_game(self, place_index, player):
        pass

    def on_confirm_left_the_room(self):
        pass

    def on_player_left_the_room(self, user_id, player):
        pass

    def on_message(self, message_type, text, sender_id, color_index, receiver_id):
        pass

    def on_show_message_dialog(self, dialog_type, title, text):
        pass

    def on_show_ok_message_dialog(self, title, text):
        pass

    def on_show_ok_cancel_message_dialog(self, title, text):
        pass

    def on_log(self, log_text):
        pass

    # Game

    def on_ready_to_start(self, place_index, is_ready, start_game_countdown_sec):
        pass

    def on_reset_game(self):
        pass

    def on_change_player_turn(self, place_index, player, turn_timeout_sec):
        pass

    def on_show_cashbox_dialog(self):
        pass

    def on_player_wins(self, place_index, player, money_win, player_money_in_play):
        pass

    def on_player_wins_the_tournament(self, place_index, player, money_win):
        pass

    def on_update1(self, *args):
        pass

    def on_update2(self, *args):
        pass

    def on_raw_binary_update(self, raw_binary):
        pass

    # Send

    def auth(self):
        self.send([client_commands.AUTHORIZE, self.credentials.user_id, self.credentials.social_id,
                   self.credentials.access_token, self.credentials.auth_sig,
                   self.credentials.backend, self.credentials.session_id])

    def update_self_user_info(self):
        self.send([client_commands.UPDATE_SELF_USER_INFO])

    def get_lobby_info_list(self):
        self.send([client_commands.GET_LOBBY_INFO_LIST])

    def change_lobby(self, lobby_id=-1):
        self.send([client_commands.CHANGE_LOBBY, lobby_id])

    def get_rooms_list(self):
        self.send([client_commands.GET_ROOMS_LIST])

    def find_free_room(self, find_and_join=FindAndJoin.JOIN_ROOM, room_code="", max_stake=0):
        self.send([client_commands.FIND_FREE_ROOM, find_and_join, room_code, max_stake])

    def get_room_info(self, room_id):
        self.send([client_commands.GET_ROOM_INFO, room_id])

    def create_room(self, room_info):
        self.send([client_commands.CREATE_ROOM, room_info])

    def edit_room(self, room_id, room_info):
        self.send([client_commands.EDIT_ROOM, room_id, room_info])

    def delete_room(self, room_id):
        self.send([client_commands.DELETE_ROOM, room_id])

    def get_game_info(self, room_id="", is_get_room_content=0):
        self.send([client_commands.GET_GAME_INFO, room_id, is_get_room_content])

    def get_player_info(self, place_index, room_id=""):
        self.send([client_commands.GET_PLAYER_INFO, place_index, room_id])

    def join_the_room(self, room_id, password=None):
        self.send([client_commands.JOIN_THE_ROOM, room_id, password])

    def join_the_game(self, room_id="", password=None, place_index=-1, money_in_play=0):
        self.send([client_commands.JOIN_THE_GAME, room_id, password, place_index, money_in_play])

    def leave_the_game(self):
        self.send([client_commands.LEAVE_THE_GAME])

    def leave_the_room(self):
        self.send([client_commands.LEAVE_THE_ROOM])

    def invite_friends_to_room(self):
        # todo
        self.send([client_commands.INVITE_FRIENDS_TO_ROOM])

    def send_message(self, message_type, text, receiver_id=-1):
        self.send([client_commands.SEND_MESSAGE, message_type, text, receiver_id])

    def ready_to_start(self, is_ready):
        self.send([client_commands.READY_TO_START, is_ready])

    def action1(self, *args):
        self.send([client_commands.ACTION1, *args])

    def action2(self, *args):
        self.send([client_commands.ACTION2, *args])

    def raw_binary_action(self, raw_binary):
        self.send([client_commands.RAW_BINARY_ACTION, raw_binary])
