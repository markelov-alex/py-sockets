import hashlib
import json
import os
from collections import defaultdict

import napalm.play.service
from napalm.async import Timer
from napalm.core import BaseModel, ExportableMixIn
from napalm.play.game import Game, BaseGameConfig
from napalm.play.protocol import MessageCode, MessageType
from napalm.socket.parser import CommandParser
from napalm.socket.protocol import Protocol
from napalm.socket.server import ServerConfig
from napalm.utils import object_util


class LobbyModel(ServerConfig, BaseModel):
    """
    Each server has its lobby, and only one lobby per server.
    """

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def room_info_list(self):
        # (str(self.lobby_id) - because dict was taken from json, where all keys must be strings)
        lobby_id = str(self.lobby_id)
        return self._room_info_list_by_lobby_id[lobby_id] \
            if self._room_info_list_by_lobby_id and lobby_id in self._room_info_list_by_lobby_id else []

    @property
    def lobby_info_list(self):
        # Update _lobby_info_dic_by_lobby_id with data from current model
        object_util.set_up_object(self._lobby_info_dic_by_lobby_id[self.lobby_id], self,
                                  self._public_export_property_name_list)

        # Convert _lobby_info_dic_by_lobby_id with current lobby states to plain lobby_info_list
        result = []
        lobby_id_list = sorted(self._lobby_info_dic_by_lobby_id.keys())
        for lobby_id in lobby_id_list:
            lobby_state = self._lobby_info_dic_by_lobby_id[lobby_id]
            result.append(object_util.object_to_plain_list(lobby_state, self._public_export_property_name_list))
        return result

    @property
    def _config_property_name_list(self):
        # -(The first item is lobby_id, but we skip it because it's set in constructor)
        # -return ["", "lobby_name", "_host", "_port", "allow_guest_auth", "allow_multisession",
        #         "allow_multisession_in_the_room", "save_lobby_state_enabled", "save_lobby_state_on_any_change",
        #         "restore_lobby_state_on_start", "continue_game_on_user_reconnect"]
        return ["lobby_id", "lobby_name", "_host", "_port", "allow_guest_auth", "allow_multisession",
                "allow_multisession_in_the_room", "save_lobby_state_enabled", "save_lobby_state_on_any_change",
                "restore_lobby_state_on_start", "continue_game_on_user_reconnect"]

    @property
    def _public_export_property_name_list(self):
        # (The first item is lobby_id, but we skip it because it's set in constructor)
        return ["lobby_id", "lobby_name", "_host", "_port", "players_online"]

    def __init__(self, default_host="", default_port=0,
                 lobby_id=0, data_dir_path=None, **kwargs):
        ServerConfig.__init__(self, default_host, default_port)
        self.lobby_id = int(lobby_id)
        self._data_dir_path = data_dir_path or ""

        # Define subclasses
        self.command_parser_class = CommandParser
        self.lobby_class = Lobby
        self.room_class = Room
        self.game_class = Game
        self.player_class = Player
        self.user_class = User
        self.timer_class = Timer

        # Loading data configuring lobby, rooms and games
        self.backends_json_path = "backends.json"
        self.servers_json_path = "servers.json"
        self.rooms_json_path = "rooms.json"
        self.games_json_path = "games.json"

        # # Backend is a php server to which we should make requests to save any game progress
        # self.backend_domain = None
        # # Social app secret (to check auth_sig)
        # self.app_secret = None
        # # Secret key to make secured requests to php server
        # self.napalm_secret = None

        self._backend_info_by_backend = {}
        self._lobby_info_list = []
        self._room_info_list_by_lobby_id = {}
        self.game_config_by_type = {}

        self._lobby_info_dic_by_lobby_id = {}

        # kwargs - to set up properties above (xxx_class, xxx_path)
        object_util.set_up_object(self, kwargs)

        # Default config values
        self.lobby_name = None
        # Allow user to play without authorizing
        self.allow_guest_auth = True
        # Allow playing from same user account on current server from multiscreen client,
        # multiple devices or multiple browser tabs
        self.allow_multisession = True
        # Allow playing from same user account in same room (allow user playing with himself)
        self.allow_multisession_in_the_room = False
        # -self.allow_same_user_in_the_room = False

        # Allow to restore and continue all games after server restart or some failure
        self.save_lobby_state_enabled = True
        self.save_lobby_state_on_exit = True
        # (Don't use this in release version if lobby saves state to file)
        self.save_lobby_state_on_any_change = True
        self.restore_lobby_state_on_start = True
        # (Allow to continue play on client reconnect: Don't dispose user instance immediately on disconnect)
        self.continue_game_on_user_reconnect = True
        # Player will be disposed on timeout. Set 0 to disable timeout
        # self.player_reconnect_timeout_sec = 0

        # State
        self.players_online = 0

        self._load_data()
        # BaseModel.__init__(self, None)

    def __repr__(self):
        config = ""
        # config = " multisession:{0} restore:{1} reconnect:{2}".format(
        #     int(self.allow_multisession), int(self.save_lobby_state_enabled and self.restore_lobby_state_on_start),
        #     int(self.continue_game_on_user_reconnect))
        return "<{0} id:{1} name:{2} players_online:{3}>".format(
            self.__class__.__name__, self.lobby_id, self.lobby_name, self.players_online) + config

    def reload(self):
        """
        We can update server without restart if some params in json changed.
        After that program will use new params whenever it get them through
        config instance of this class. To apply also old values we nee to
        restart the server.
        """
        self._load_data()
        self.reset()

    def _load_data(self):
        path_prefix = os.path.join(os.getcwd(), self._data_dir_path or '')
        # path_prefix = path_prefix.replace(os.sep, os.altsep)
        # (Fixes _data_dir_path if needed)
        path_prefix = path_prefix.replace(os.altsep, os.sep)

        backends_full_path = os.path.join(path_prefix, self.backends_json_path)
        servers_full_path = os.path.join(path_prefix, self.servers_json_path)
        rooms_full_path = os.path.join(path_prefix, self.rooms_json_path)
        games_full_path = os.path.join(path_prefix, self.games_json_path)

        print("C (_load_data) data_dir_path:", self._data_dir_path, "servers_full_path:", servers_full_path,
              "rooms_full_path:", rooms_full_path)
        self.set_data(self._load_json(backends_full_path),
                      self._load_json(servers_full_path),
                      self._load_json(rooms_full_path),
                      self._load_json(games_full_path))

    def _load_json(self, json_path):
        if not json_path:
            return None

        try:
            result = json.load(open(json_path))
        except Exception as error:
            result = None
            print("Error while loading JSON by path:", json_path, "error:", error)
        return result

    def _apply_initial_config(self):
        # print("Select lobby info by lobby_id:", lobby_id)
        self._initial_config = self._get_lobby_info_by_lobby_id(self.lobby_id) or None  # self._initial_config
        if not self._initial_config:
            # print("ERROR! lobby_info_list contains no item with lobby_id:", lobby_id)
            raise Exception("ERROR! lobby_info_list contains no item with lobby_id: " + str(self.lobby_id))
        print("C (_apply_data) Set lobby_data:", self._initial_config, "of lobby_id:", self.lobby_id)

        super()._apply_initial_config()

    def set_data(self, backend_info_list=None, lobby_info_list=None, room_info_list_by_lobby_id=None, game_config_by_type=None):
        """
        You can set all the data manually from code without loading json files.
        """
        self._backend_info_by_backend = backend_info_list or self._backend_info_by_backend
        self._lobby_info_list = lobby_info_list or self._lobby_info_list
        self._room_info_list_by_lobby_id = room_info_list_by_lobby_id or self._room_info_list_by_lobby_id
        self.game_config_by_type = game_config_by_type or self.game_config_by_type

        # Update _lobby_info_dic_by_lobby_id
        for lobby_info in self._lobby_info_list:
            lobby_info_dic = dict()
            object_util.set_up_object(lobby_info_dic, lobby_info, self._config_property_name_list)
            self._lobby_info_dic_by_lobby_id[lobby_info_dic["lobby_id"]] = lobby_info_dic

        self.reset()

    def get_backend_info(self, backend=None):
        if not backend and "default" in self._backend_info_by_backend:
            backend = self._backend_info_by_backend["default"]
        if backend and backend in self._backend_info_by_backend:
            return self._backend_info_by_backend[backend]
        print("C WARNING! (get_backend_info) There is no backend_info in backends.json for backend:", backend)

        return None

    def update_lobby_info(self, lobby_id=-1, **kwargs):
        # To set players_online for other lobbies
        lobby_info_dic = self if lobby_id < 0 or lobby_id == self.lobby_id else \
            self._get_lobby_info_by_lobby_id(lobby_id)
        if not lobby_info_dic:
            return

        object_util.set_up_object(lobby_info_dic, kwargs, self._public_export_property_name_list)

    def _get_lobby_info_by_lobby_id(self, lobby_id):
        lobby_info_list = [item for item in self._lobby_info_list if lobby_id == item[0]]
        lobby_info = lobby_info_list[0] if lobby_info_list else None
        return lobby_info


class PlayerManager:
    """
    session_id = 0, 1, ..., N;  -1 or None will be considered as default: 0
    """

    @property
    def players_online(self):
        # return len(self.player_by_session_id_by_user_id)
        return len(self.player_set) - len(self.disconnected_player_set)

    def __init__(self, lobby_model):
        # Model
        self.lobby_model = lobby_model
        """:type: LobbyModel"""

        if not Protocol.dummy_protocol:
            Protocol.dummy_protocol = self.lobby_model.protocol_class()

        # ??
        self.user_info_by_user_id = None

        self.user_by_user_id = {}
        self.user_use_count_by_user_id = {}

        # All authorized players (online + temporarily offline)
        self.player_set = set()
        self.player_by_session_id_by_user_id = defaultdict(dict)
        # Temporarily offline players (disconnected)
        self.disconnected_player_set = set()
        # self.disconnected_player_by_session_id_by_user_id = defaultdict(dict)

        # State
        self.is_restoring_now = False

    def dispose(self):
        for player in self.player_set:
            player.dispose()
        for player in self.disconnected_player_set:
            player.dispose()
        # -for player in self.player_by_session_id_by_user_id.values():
        #     player.dispose()
        # for player in self.disconnected_player_by_session_id_by_user_id.values():
        #     player.dispose()

        for user in self.user_by_user_id.values():
            user.dispose()

        self.user_info_by_user_id.clear()

        self.user_by_user_id.clear()
        self.user_use_count_by_user_id.clear()
        self.player_set.clear()
        self.player_by_session_id_by_user_id.clear()
        self.disconnected_player_set.clear()
        # self.disconnected_player_by_session_id_by_user_id.clear()

        self.is_restoring_now = False

        # Model
        self.lobby_model = None

    def __repr__(self):
        return "<{0} lobby_id:{1} player_count:{2}>".format(
            self.__class__.__name__, self.lobby_model.lobby_id, len(self.player_by_session_id_by_user_id))

    def get_player(self, user_id, session_id=-1):
        # if not self.lobby_model.allow_multisession:
        #     session_id = 0
        if session_id < 0 or session_id is None:
            session_id = 0
        return self.player_by_session_id_by_user_id[user_id].get(session_id)

        # -for player in self.player_set:
        #     if player.user_id == user_id and (session_id < 0 or player.session_id == session_id):
        #         return player
        # return None

    def _pop_disconnected_player(self, user_id, session_id=-1):
        # if not self.lobby_model.allow_multisession:
        #     session_id = 0
        if session_id < 0 or session_id is None:
            session_id = 0

        # player_by_session_id = self.disconnected_player_by_session_id_by_user_id[user_id]
        # player = player_by_session_id.pop(session_id) if session_id in player_by_session_id else None
        # return player

        for player in self.disconnected_player_set:
            if player.user_id == user_id and (session_id < 0 or player.session_id == session_id):
                self.disconnected_player_set.remove(player)
                return player
        return None

    # def generate_auth_sig(self, social_id, access_token):
    #     md5 = hashlib.md5()
    #     md5.update(social_id + "_" + access_token + "_" + self.lobby_model.app_secret)
    #     return md5.hexdigest()

    def create_player(self, user_id, social_id=None, access_token=None, auth_sig=None, 
                      backend=None, session_id=-1, protocol=None):
        """
        :param user_id:
        :param session_id: define to reconnect previous session or to create new.
                            Omit at first connect to create new session
        :param protocol:
        :return:
        """
        # CENSORED

    # Called from protocol on disconnect
    def remove_player(self, player):
        print("L -temp LOBBY_REMOVING_USER (remove_player)",
              "player_set:", [player for player in self.player_set], "player:", player,
              "continue_game_on_user_reconnect:", self.lobby_model.continue_game_on_user_reconnect,
              "and (",  # "player_reconnect_timeout_sec:", self.lobby_model.player_reconnect_timeout_sec, "or",
              "player.play:", player.game, ")")
        # (Note: We can dispose disconnected players later only on timeout or when the player looses the play)
        if self.lobby_model.continue_game_on_user_reconnect and (  # self.lobby_model.player_reconnect_timeout_sec > 0 or
                player.game):
            self.disconnected_player_set.add(player)
            # self.disconnected_player_by_session_id_by_user_id[player.user_id][player.session_id] = player
        else:
            player.dispose()
            # todo! check and dispose disconnected players on timeout
    #
    # # Called if player loose the play while was disconnected
    # def dispose_player(self, player):
    #     print("L temp (dispose_player) player:", player, "in?:", player in self.player_set,
    #           "player_set:", self.player_set)
    #     if player not in self.player_set:
    #         return
    #
    #     self.on_player_dispose(player)
    #
    #     # return self.player_manager.remove(player, True)
    #     player.dispose()
    #     return player

    # Override
    def on_player_dispose(self, player):
        user_id = player.user_id
        session_id = player.session_id

        print("L temp  (on_player_dispose) ", "player:", player)
        # if player in self.player_set:
        self.player_set.remove(player)
        if player in self.disconnected_player_set:
            self.disconnected_player_set.remove(player)

        player_by_session_id = self.player_by_session_id_by_user_id[user_id]
        player_by_session_id.pop(session_id) if session_id in player_by_session_id else None
        # player_by_session_id = self.disconnected_player_by_session_id_by_user_id[user_id]
        # player_by_session_id.pop(session_id) if session_id in player_by_session_id else None


class RoomManager:
    def __init__(self, lobby_model):
        # Model
        self.lobby_model = lobby_model
        """:type: LobbyModel"""

        self.room_by_id = {}
        self.room_list = []

        # Create rooms
        for room_info in self.lobby_model.room_info_list:
            self._create_room(room_info)

    def dispose(self):
        for room in self.room_by_id.values():
            room.dispose()
        self.room_by_id = {}
        self.room_list = []

        # Model
        self.lobby_model = None

    def __repr__(self):
        return "<{0} lobby_id:{1} room_count:{2}>".format(
            self.__class__.__name__, self.lobby_model.lobby_id, len(self.room_by_id))

    # List to be serialized
    def rooms_export_data(self):
        print("L rooms_export_data room_by_id:", self.room_by_id, "room_list:", self.room_list)
        return [room.room_model.export_data() for room in self.room_list]

    def create_private_room(self, player, room_info):
        owner_user_id = player.user_id
        # That means that each player can have only one private room now
        room_id = "pr_" + owner_user_id
        # room_info[0] = room_id
        room_info.insert(0, room_id)
        # todo check is private in room_code
        if self._create_room(room_info):
            self.get_room_info(player, room_id)
        else:
            print("L WARNING! (create_private_room) Failed to create the room with room_info:", room_info,
                  "for player:", player)
            self.get_room_info(player, None)

    def edit_private_room(self, player, room_info):
        room_id = room_info[0]
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        if room:
            room.change(room_info)
            self.get_room_info(player, room_id)
        else:
            print("L WARNING! (edit_private_room) There is no room with room_id:", room_id,
                  "from room_info:", room_info, "player:", player)
            self.get_room_info(player, None)

    def delete_private_room(self, player, room_id):
        if self._remove_room(room_id):
            self.get_room_list(player)
        else:
            print("L WARNING! (delete_private_room) Cannot remove the room with room_id:", room_id, "player:", player)

    # Create/remove items

    def _create_room(self, room_info):
        # CENSORED
        return True

    def _remove_room(self, room_id):
        # CENSORED
        return False


class SaveLoadLobbyStateMixIn:
    def try_save_lobby_state_on_change(self):
        if self.lobby_model.save_lobby_state_on_any_change and not self.is_restoring_now:
            self.save_lobby_state()

    def save_lobby_state(self):
        if not self.lobby_model.save_lobby_state_enabled:
            print("L (save_lobby_state) Saving disabled. "
                  "lobby_model.save_lobby_state_enabled:", self.lobby_model.save_lobby_state_enabled, self)
            return

        print("L =(SAVE_lobby_state) Start", self)
        # Save users
        user_id_by_session_id_list = []
        user_info_by_user_id = dict()

        for player in self.player_set:
            user_id_by_session_id_list.append([player.user_id, player.session_id])
            user_info_by_user_id[player.user_id] = player.export_data(False)

        # Save rooms and games
        room_data_by_room_id = dict()
        for room_id, room in self.room_by_id.items():
            # Players
            visitor_list = []
            player_data_by_place_index = dict()
            for player in room.player_set:
                if not player.game:
                    visitor_list.append([player.user_id, player.session_id])
                else:
                    player_data_by_place_index[player.place_index] = [player.user_id, player.session_id]

            # Game
            game_data = room.game.export_data(is_public=False) if room.game else None
            # print("temp (save_lobby_state) room_id:", room_id, "room.play:", room.play, "game_data:", game_data)

            room_data = {"visitor_list": visitor_list, "player_data_by_place_index": player_data_by_place_index,
                         "game_data": game_data}
            room_data_by_room_id[room_id] = room_data

        lobby_state_json = {"user_id_by_session_id_list": user_id_by_session_id_list,
                            "user_info_by_user_id": user_info_by_user_id,
                            "room_data_by_room_id": room_data_by_room_id}
        self._save_lobby_state_object(lobby_state_json)
        print("=(save_lobby_state) End", self)

    def restore_lobby_state(self):
        if not self.lobby_model.save_lobby_state_enabled or not self.lobby_model.restore_lobby_state_on_start:
            print("L (restore_lobby_state) Saving and restoring disabled.",
                  "lobby_model.save_lobby_state_enabled:", self.lobby_model.save_lobby_state_enabled,
                  "lobby_model.restore_lobby_state_on_start:", self.lobby_model.restore_lobby_state_on_start, self)
            return

        self.is_restoring_now = True
        lobby_state_json = self._load_lobby_state_object()
        if lobby_state_json:
            print("L =(RESTORE_lobby_state) Start", self)
            # Restore users
            user_id_by_session_id_list = lobby_state_json["user_id_by_session_id_list"]
            self.user_info_by_user_id = lobby_state_json["user_info_by_user_id"]
            print("temp (restore_lobby_state) user_id_by_session_id_list:", user_id_by_session_id_list)
            print("temp (restore_lobby_state) self.user_info_by_user_id:", self.user_info_by_user_id)
            for user_id, session_id in user_id_by_session_id_list:
                self.create_player(user_id, session_id=session_id)

            # Restore rooms and games
            room_data_by_room_id = lobby_state_json["room_data_by_room_id"]
            for room_id, room_data in room_data_by_room_id.items():
                visitor_list = room_data["visitor_list"]
                player_data_by_place_index = room_data["player_data_by_place_index"]
                room = self.room_by_id[room_id]
                room_password = room.room_model.room_password
                print("temp (restore_lobby_state) room:", room, "visitor_list:", visitor_list,
                      "player_data_by_place_index:", player_data_by_place_index)

                # Join visitors to room (not players)
                for user_id, session_id in visitor_list:
                    player = self.get_player(user_id, session_id)
                    print("temp  (restore_lobby_state) join_the_room room_id:", room_id, "player:", player)
                    self.join_the_room(player, room_id, room_password)

                # Join players to play
                for place_index in player_data_by_place_index:
                    user_id, session_id = player_data_by_place_index[place_index]
                    player = self.get_player(user_id, session_id)
                    print("temp  (restore_lobby_state) join_the_Game room_id:", room_id, "player:", player,
                          "place_index:", int(place_index))
                    self.join_the_game(player, room_id, room_password, int(place_index))

                # Restore play
                game_data = room_data["game_data"]
                print("temp  (restore_lobby_state) play.import_data game_data:", game_data, "room.play:", room.game)
                if game_data and room.game:
                    room.game.import_data(game_data)
                    # todo restore play after delay
                    # room.play.restore_game()

            print("L =(restore_lobby_state) End", self)

        self.is_restoring_now = False

    # todo use memecache instead saving to file
    # Override
    def _save_lobby_state_object(self, lobby_state_json):
        filename = "dumps/" + self.lobby_model.lobby_name + "_state_dump.json"
        dir_name = os.path.dirname(filename)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        json.dump(lobby_state_json, open(filename, "w"))

    # todo use memecache instead saving to file
    # Override
    def _load_lobby_state_object(self):
        filename = "dumps/" + self.lobby_model.lobby_name + "_state_dump.json"
        if not os.path.exists(filename):
            print("L (_load_lobby_state_object) There is no json file with lobby state data. filename:", filename,
                  self)
            return None
        return json.load(open(filename))


class Lobby(SaveLoadLobbyStateMixIn, PlayerManager, RoomManager):
    def __init__(self, lobby_model):
        # Model
        self.lobby_model = lobby_model
        """:type: LobbyModel"""

        print("L Create Lobby", self.lobby_model.lobby_id)  # , self.lobby_model.room_info_list)
        PlayerManager.__init__(self, lobby_model)
        RoomManager.__init__(self, lobby_model)
        # Players
        # todo remake
        # self.player_manager = PlayerManager(self.lobby_model.player_class, self.lobby_model.user_class,
        #                                     # todo get value each time from self.lobby_model
        #                                     self.lobby_model.allow_guest_auth)

        # temp

    def dispose(self):
        PlayerManager.dispose(self)
        RoomManager.dispose(self)

        # Model
        self.lobby_model = None

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_count:{3} player_count:{4}>".format(
            self.__class__.__name__, self.lobby_model.lobby_id, self.lobby_model.lobby_name,
            len(self.room_by_id), len(self.player_set))

    # Override
    def on_player_dispose(self, player):
        if player.room:
            self.leave_the_room(player)

        super().on_player_dispose(player)

    # Restore player after client reconnection (send needed messages to client)
    def check_restore_player(self, player):
        if not player.is_just_restored:
            return

        player.is_just_restored = False

        print("L temp (restore_player) player:", player)
        if player.game:
            self.join_the_game(player)
        elif player.room:
            self.join_the_room(player)

    def start(self):
        if self.lobby_model.restore_lobby_state_on_start:
            self.restore_lobby_state()

    # Protocol process methods (Lobby)

    def get_lobby_info_list(self, player):
        print("L (get_lobby_info_list)", "lobby_id:", self.lobby_model.lobby_id,
              "lobby_info_list:", self.lobby_model.lobby_info_list)

        player.protocol.lobby_info_list(self.lobby_model.lobby_id, self.lobby_model.lobby_info_list)

    # Protocol process methods (Room)

    def get_room_list(self, player):
        player.protocol.rooms_list(self.rooms_export_data())

    def find_free_room(self, player, find_and_join, game_id=-1, game_type=-1, room_type=-1):
        """
        :param player
        :param find_and_join 0-just find, 1-find and join a room, 2-find and join a play
        :param game_id
        :param game_type
        :param room_type
        """
        # CENSORED

    def get_room_info(self, player, room_id):
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        player.protocol.room_info(room.export_data())

    def get_game_info(self, player, room_id, is_get_room_content=False):
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        if room:
            room.get_game_info(player, is_get_room_content)
        else:
            player.protocol.game_info(None, None)

    def get_player_info_in_game(self, asking_player, room_id, place_index):
        room = self.room_by_id[room_id]
        if not room:
            print("L WARNING! (get_player_info_in_game) There is no room with room_id:", room_id)
            return
        if not room.game:
            # If play not created hence there are no players in it
            asking_player.protocol.player_info(place_index, None)
        else:
            room.game.get_player_info(asking_player, place_index)

    def join_the_room(self, player, room_id=None, password=None):
        if not room_id:
            room = player.room
        else:
            room_id = str(room_id)
            room = self.room_by_id[room_id] if room_id in self.room_by_id else None

        # CENSORED
        return room

    def join_the_game(self, player, room_id=None, password=None, place_index=-1, money_in_play=0):
        room = self.join_the_room(player, room_id, password)
        if room:
            room.join_the_game(player, place_index, money_in_play)
            if player.is_connected:
                print("L (join_the_game) [try_save] player:", player)
                self.try_save_lobby_state_on_change()
        else:
            print("L WARNING! (join_the_game) Cannot join! Player didn't joined the room:", room, "for player:", player)

    def leave_the_game(self, player):
        room = player.room if player else None
        if room:
            room.leave_the_game(player)
            if player.is_connected:
                print("L (leave_the_game) [try_save] player:", player)
                self.try_save_lobby_state_on_change()
        else:
            print("L WARNING! (leave_the_game) Cannot leave! Player not in the room:", room, "for player:", player)

    def leave_the_room(self, player):
        room = player.room if player else None
        if room:
            room.remove_player(player)
            if player.is_connected:
                print("L (leave_the_room) [try_save] player:", player)
                self.try_save_lobby_state_on_change()
        else:
            print("L WARNING! (leave_the_room) Cannot leave! Player not in the room:", room, "for player:", player)

    def send_message(self, message_type, text, sender_player, receiver_id=-1, is_check_security=False):
        # is_check_security - to check params received from network to avoid spamming

        if message_type == MessageType.MSG_TYPE_MAIL:
            if is_check_security:
                # todo check either receiver is a friend of sender (security)
                pass
            # todo save mail in php server
            pass

        if receiver_id >= 0 and message_type >= MessageType.MSG_TYPE_PRIVATE:
            # Private personal messages
            # todo use session_id
            # ??--todo broadcast somehow to all player sessions of current user (?) -
            # all browser tabs/devices should receive the message (?)
            receiver_user = self.get_player(receiver_id)
            if receiver_user:
                receiver_user.protocol.send_message(message_type, text, sender_player)
            else:
                print("L temp (lobby.send_message) Player is offline.",
                      "To be send through php server" if message_type == MessageType.MSG_TYPE_MAIL else "")
        else:
            # Public personal and broadcast messages
            room = sender_player.room
            if room:
                # In the room
                room.send_message(message_type, text, sender_player, receiver_id)
            else:
                # In the lobby
                for player in self.player_set:
                    if not player.room:
                        player.protocol.send_message(message_type, text, sender_player, receiver_id)
                        # print("WARNING! (send_message) Wrong message_type:", message_type, "sender_user:",
                        #       sender_user, "text:", text, "receiver_index:", receiver_index)


# Protocol send methods (Room)
class RoomSendMixIn:
    def send_player_joined_the_room(self, joined_player, exclude_players=None):
        for player in self.player_set:
            if exclude_players and player not in exclude_players:
                protocol = player.protocol
                print("R (send_player_joined_the_room)", player, player.protocol)
                """:type : GameProtocol"""
                protocol.player_joined_the_room(joined_player.export_data())

    def send_player_joined_the_game(self, joined_player):  # , is_reconnect=False
        # if not is_reconnect:
        #     log_text = " ".join((joined_player.first_name, joined_player.last_name,
        #                         joined_player.user_id, "joined the play"))

        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.player_joined_the_game(joined_player.place_index, joined_player.export_data())  # , log_text

    def send_player_left_the_game(self, left_player):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.player_left_the_game(left_player.place_index)

    def send_player_left_the_room(self, left_player, exclude_players=None):
        for player in self.player_set:
            if exclude_players and player not in exclude_players:
                protocol = player.protocol
                """:type : GameProtocol"""
                protocol.player_left_the_room(left_player.place_index)

    def send_message(self, message_type, text, sender_player, receiver_id=-1):
        is_message_private = MessageType.is_message_private(message_type)
        for player in self.player_set:
            if not is_message_private or player.user_id == receiver_id:
                player.protocol.send_message(message_type, text, sender_player, receiver_id)

    def send_log(self, log_text):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.send_log(log_text)

    # Protocol send methods (Game)

    def send_reset_game(self):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.reset_game()

    def send_change_player_turn(self, player_in_turn_index, turn_timeout_sec):
        print("R (send_change_player_turn)  room:", self)
        if self.on_game_state_changed:
            print("R (send_change_player_turn) [try_save] room:", self)
            self.on_game_state_changed()
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.change_player_turn(player_in_turn_index, turn_timeout_sec)

    def send_player_wins(self, place_index, money_win, player_money_in_play):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.player_wins(place_index, money_win, player_money_in_play)

    def send_player_wins_the_tournament(self, place_index, money_win):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.player_wins_the_tournament(place_index, money_win)

    def send_update1(self, *args):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.update1(*args)

    # ?? if private - remove
    def send_update2(self, *args):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.update2(*args)

    def send_raw_binary_update(self, raw_binary):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.raw_binary_update(raw_binary)


class RoomModel(BaseModel):
    # default_pot_limit = ""  # todo!?

    @property
    def is_password_needed(self):
        return bool(self.room_password)

    @property
    def visitor_count(self):
        return self.total_player_count - self.playing_count

    @property
    def _config_property_name_list(self):
        return ["room_id", "room_name", "room_code", "game_params",
                "max_playing_count", "max_visitor_count", "room_password",
                "turn_timeout_sec"]

    @property
    def _public_export_property_name_list(self):
        return ["room_id", "room_name", "room_code", "game_params",
                "max_playing_count", "max_visitor_count", "is_password_needed",
                "playing_count", "visitor_count",
                "turn_timeout_sec", "end_round_delay_sec"]

    @property
    def _game_property_name_list(self):
        """
        Rule 1: keep order same as in json config file (rooms.json)
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return ["min_stake", "max_stake"]

    def __init__(self, initial_config):
        # Set default config values
        self.room_id = ""
        self.room_name = ""
        self.room_code = ""
        # (Temp var to export and import game_param vars)
        self.game_params = []
        #  -1 - unbounded
        self.max_playing_count = -1
        self.max_visitor_count = -1
        # for private rooms
        self.room_password = ""

        # game_params parsed
        # Small blind stake for poker
        self.min_stake = 0
        # Big blind stake for poker
        self.max_stake = 0

        # Timing
        self.turn_timeout_sec = 10
        self.end_round_delay_sec = 1
        self.show_winner_delay_sec = 1
        self.end_game_delay_sec = 1

        # room_code parsed
        self.game_id = None
        self.game_type = None
        self.room_type = None

        self.is_private = False
        # "" - for public, checked before returning room info list to specified player
        # (for some games only owners can see their rooms (is_private==True))
        self.owner_user_id = ""

        # State
        self.total_player_count = 0
        self.playing_count = 0
        # -self.visitor_count = 0

        # Set up
        super().__init__(initial_config)

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_code:{3} max_players:{4}>".format(
            self.__class__.__name__, self.room_id, self.room_name, self.room_code, self.max_playing_count)

    def _apply_initial_config(self):
        super()._apply_initial_config()

        # Parse game_params
        object_util.set_up_object(self, self.game_params, self._game_property_name_list)

        # Parse room_code
        self.game_id, self.game_type, self.room_type = CommandParser.parse_room_code(self.room_code)
        # print(self, "_initial_config:", self._initial_config, "self._config_property_name_list:",
        #       self._config_property_name_list)
        # print("  parsed", "game_id:", self.game_id, "game_type:", self.game_type, "room_type:", self.room_type)

    def import_data(self, data_list):
        if not data_list:
            print("Rm WARNING! (import_data) Wrong data_list:", data_list)
            return

        super().import_data(data_list)

        # Parse game_params
        object_util.set_up_object(self, self.game_params, self._game_property_name_list)

        # Parse room_code
        self.game_id, self.game_type, self.room_type = CommandParser.parse_room_code(self.room_code)
        print(self, "data_list:", data_list)
        print("  parsed", "game_id:", self.game_id, "game_type:", self.game_type, "room_type:", self.room_type)

    def export_data(self, is_public=True):
        # Update game_params before it will be exported
        self.game_params = object_util.object_to_plain_list(self, self._game_property_name_list)

        return super().export_data(is_public)


class Room(RoomSendMixIn):
    room_model_class = RoomModel
    game_config_class = BaseGameConfig

    @property
    def has_free_seat_to_play(self):
        return self.room_model.max_playing_count < 0 or \
               (self.game and len(self.game.player_list) < self.room_model.max_playing_count)

    @property
    def is_empty_room(self):
        return self.room_model.max_playing_count > 0 and (not self.game or not len(self.game.player_list))

    #
    # @property
    # def total_player_count(self):
    #     return len(self.player_set)
    #
    # @property
    # def playing_count(self):
    #     return len(self.play.player_list) if self.play else 0
    #
    # @property
    # def visitor_count(self):
    #     return self.total_player_count - self.playing_count

    def __init__(self, lobby_model, room_config):
        self.lobby_model = lobby_model
        self.room_model = room_config if isinstance(room_config, RoomModel) else self.room_model_class(room_config)
        self.game_config = self.game_config_class(self.room_model.game_id, self.room_model.game_type,
                                                  self.lobby_model.game_config_by_type)

        # Players added/removed
        self.player_set = set()  # type: set(Player)
        # Game created/disposed
        self.game = None
        """:type: Game"""

        self.on_game_state_changed = None

    def dispose(self):
        self.lobby_model = None
        self.remove_all_players()

        # todo dispose all vars

        self.on_game_state_changed = None

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_code:{3} players:{4}/{5}>".format(
            self.__class__.__name__, self.room_model.room_id, self.room_model.room_name, self.room_model.room_code,
            self.room_model.playing_count, self.room_model.max_playing_count)

    # def change(self, room_info):
    #     self.remove_all_players()
    #     self.room_model.set_up??(room_info)

    # Players

    def add_player(self, player, password=None):
        print("R (add_player) player:", player, "self.player_set:", self.player_set)
        # CENSORED

    def remove_player(self, player):
        if player.game:
            self.leave_the_game(player)
        # CENSORED
        return False

    def remove_all_players(self):
        # player_list = list(self.player_set)
        for player in self.player_set:
            self.remove_player(player)

    # Game

    def get_game_info(self, player, is_get_room_content=False):
        """
        :param player:
        :param is_get_room_content: can reset empty place while get_all_player_info() can't
        :return:
        """

        game_info = self.game.export_data(for_place_index=player.place_index) if self.game else None
        player_info_list = [player.export_data() if player else []
                            for player in self.game.player_by_place_index_list] \
            if self.game and is_get_room_content else None

        player.protocol.game_info(game_info, player_info_list)

    def join_the_game(self, player, place_index=-1, money_in_play=0):
        if player not in self.player_set:
            print("R WARNING! (join_the_game) Cannot join the play! Player not in player_set:",
                  self.player_set, "for player:", player)
            return False
        # (Update max_playing_count value) ?
        self.game.max_playing_count = self.room_model.max_playing_count
        result = self.game.add_player(player, place_index, money_in_play)
        if result:
            # self.room_model.playing_count += 1
            self.room_model.playing_count = len(self.game.player_list) if self.game else 0
        return result

    def leave_the_game(self, player):
        if player not in self.player_set:
            print("R WARNING! (leave_the_game) Cannot leave the play! Player not in player_set:",
                  self.player_set, "for player:", player)
            return False
        result = self.game.remove_player(player)
        if result:
            # self.room_model.playing_count -= 1
            self.room_model.playing_count = len(self.game.player_list) if self.game else 0
        return result

    def _create_game(self):
        if not self.game:
            game_class = self.lobby_model.game_class
            self.game = game_class(self, self.game_config)
            self.game._room = self

    def _finish_game(self):
        # check play wasn't finished before
        self._dispose_game()

    def _dispose_game(self):
        if self.game:
            self.game.dispose()
        self.game = None


class Player(ExportableMixIn):
    service_class = napalm.play.service.GameService
    
    # Used to muck cards on turn went to disconnected player and to kick off on new play started
    @property
    def is_connected(self):
        return self.protocol and self.protocol.is_ready

    @property
    def _export_property_name_list(self):
        # Always sync changes in client's code!
        return ["user_id", "social_id", "first_name", "last_name",
                "image_url", "image_url_small", "image_url_normal",
                "level", "money_amount", "money_in_play", "is_in_game",
                "joinedDate", "gift_image_url", "vip_days_available",
                "is_playing"]

    def __init__(self):
        # self.service = self.service_class(...)
        
        self.lobby_model = None
        self.protocol = None
        # Connection to user's main model which is single for each
        # access_token while Player can have more than one instances
        self.user = None
        self.on_player_dispose = None
        
        # Credentials for php server (user_id is social_id indeed)
        self.user_id = ""
        self.social_id = ""
        self.access_token = ""
        self.auth_sig = ""
        
        self.is_guest = False
        self.session_id = -1
        self.is_just_restored = False

        # todo move to user
        self.first_name = ""
        self.last_name = ""
        self.image_url = ""
        self.image_url_small = ""
        self.image_url_normal = ""
        self.level = -1
        self.money_amount = 0

        self.money_in_play = 0
        # todo keep is_in_game actual
        self.is_in_game = 0
        self.joinedDate = ""
        self.gift_image_url = ""
        self.vip_days_available = -1

        self.room = None
        self.game = None

        # Index of player's place in the play
        self.place_index = -1
        self.is_playing = False

    def dispose(self):
        on_player_dispose = self.on_player_dispose
        if on_player_dispose:
            self.on_player_dispose = None
            # (Dispose from lobby and user_manager)
            on_player_dispose(self)
            return

        print(self, "U temp (dispose) protocol:", self.protocol)

        if self.room:
            self.room.remove_player(self)

        # self.detach_protocol()

        self.service = None
        self.lobby_model = None
        # (To clear ref on dummy after detach_protocol())
        self.protocol = None
        self.user = None

        self.user_id = None
        self.social_id = None
        self.access_token = None
        self.auth_sig = None

        # try to reset all properties
        self.__init__()

        self.room = None
        self.game = None

        self.place_index = -1
        self.is_playing = False

    def __repr__(self):
        session_id_suffix = "(" + str(self.session_id) + ")" if self.session_id >= 0 else ""
        return "<{0} user_id:{1} protocol_id:{2} name:{3} place_index:{4}>". \
            format(self.__class__.__name__, self.user_id + session_id_suffix,
                   self.protocol.protocol_id if self.protocol else "",
                   self.first_name + (" " + self.last_name if self.last_name else ""), self.place_index)

    # Override
    def reset_game_state(self):
        # Reset state properties for current game
        pass

    def update_self_user_info(self):
        user_info = self.service.getCurrentUserFullInfo()
        self.import_data(user_info)
        self.protocol.update_self_user_info(user_info)


class User:
    def __init__(self):
        self.user_id = ""

    def dispose(self):
        self.user_id = ""

    def __repr__(self):
        return "<{0} user_id:{1}>".format(self.__class__.__name__, self.user_id)
