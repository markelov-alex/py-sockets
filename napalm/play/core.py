import json
import logging as _logging
import os

from napalm.async import ThreadedTimer
from napalm.play.game import Game, GameConfigModel
from napalm.play.house import HouseModel, House, Player, User
from napalm.play.lobby import Lobby, Room, LobbyModel, RoomModel
from napalm.play.protocol import GameProtocol
from napalm.play.service import GameService
from napalm.socket.parser import CommandParser
from napalm.socket.server import ServerConfig
from napalm.utils import object_util


# todo rename to ServerModel
class HouseConfig(ServerConfig):
    """
    Each server has its house, and only one house per server.
    """

    # Loading data configuring lobby, rooms and games
    backends_json_path = "backends.json"
    servers_json_path = "servers.json"
    lobbies_json_path = "lobbies.json"
    rooms_json_path = "rooms.json"
    games_json_path = "games.json"

    # Define subclasses
    protocol_class = GameProtocol
    command_parser_class = CommandParser
    house_class = House
    lobby_class = Lobby
    room_class = Room
    game_class = Game
    player_class = Player
    user_class = User
    service_class = GameService
    timer_class = ThreadedTimer
    # todo rename model->config
    house_model_class = HouseModel
    lobby_model_class = LobbyModel
    room_model_class = RoomModel
    game_config_model_class = GameConfigModel

    house_model = None

    def __init__(self, default_host="", default_port=0,
                 house_id=0, data_dir_path=None, **kwargs):
        ServerConfig.__init__(self, default_host, default_port)
        self.logging = _logging.getLogger("CONFIG")

        self.house_id = str(house_id)
        self._data_dir_path = data_dir_path or ""

        # kwargs - to set up properties above (xxx_class, xxx_path)
        object_util.set_up_object(self, kwargs)

        # (Needed to resolve class loading without errors (HouseModel shouldn't know about LobbyModel))
        HouseModel.lobby_model_class = self.lobby_model_class
        # HouseModel.game_config_model_class = self.game_config_model_class
        # LobbyModel.room_model_class = self.room_model_class

        # Apply model classes from config
        # (Don't override __init__ to change these classes)
        GameConfigModel.model_class = self.game_config_model_class
        RoomModel.model_class = self.room_model_class
        LobbyModel.model_class = self.lobby_model_class
        HouseModel.model_class = self.house_model_class

        # # Backend is a php server to which we should make requests to save any game progress
        # self.backend_domain = None
        # # Social app secret (to check auth_sig)
        # self.app_secret = None
        # # Secret key to make secured requests to php server
        # self.napalm_secret = None

        self._backend_info_by_backend = {}

        self._load_data()

        self.house_model = HouseModel.get_model_by_id(self.house_id)

    def __repr__(self):
        config = ""
        # config = " multisession:{0} restore:{1} reconnect:{2}".format(
        #     int(self.is_allow_multisession), int(self.is_save_house_state_enabled and self.is_restore_house_state_on_start),
        #     int(self.is_continue_on_disconnect))
        return "<{0} id:{1} name:{2} players_online:{3}>".format(
            self.__class__.__name__, self.house_id, self.house_name, self.players_online) + config

    def dispose(self):
        GameConfigModel.dispose_models()
        RoomModel.dispose_models()
        LobbyModel.dispose_models()
        HouseModel.dispose_models()

        self._backend_info_by_backend = {}

        if self.house_model:
            self.house_model.dispose()
            self.house_model = None

        self.logging = None

    def reload(self):
        """
        We can update server without restart if some params in json changed.
        After that, the program will use new params whenever it get them through
        config instance.
        """
        self._load_data()

        # -- (already deep inside load_data)
        # self.house_model.on_reload()

    def _load_data(self):
        """
        You can set all the data manually from code without loading json files.
        """
        # Paths
        path_prefix = os.path.join(os.getcwd(), self._data_dir_path or '')
        # path_prefix = path_prefix.replace(os.sep, os.altsep)
        # (Fixes _data_dir_path if needed)
        path_prefix = path_prefix.replace(os.altsep, os.sep)

        backends_full_path = os.path.join(path_prefix, self.backends_json_path)
        games_full_path = os.path.join(path_prefix, self.games_json_path)
        rooms_full_path = os.path.join(path_prefix, self.rooms_json_path)
        lobbies_full_path = os.path.join(path_prefix, self.lobbies_json_path)
        servers_full_path = os.path.join(path_prefix, self.servers_json_path)

        # Load
        # self.logging.info("C (_load_data) data_dir_path: %s servers_full_path: %s lobbies_full_path: %s",
        #                   self._data_dir_path, servers_full_path, lobbies_full_path)
        self._backend_info_by_backend = self._load_json(backends_full_path) or self._backend_info_by_backend
        GameConfigModel.on_configs_reloaded(self._load_json(games_full_path))
        RoomModel.on_configs_reloaded(self._load_json(rooms_full_path))
        LobbyModel.on_configs_reloaded(self._load_json(lobbies_full_path))
        HouseModel.on_configs_reloaded(self._load_json(servers_full_path))
        # self.logging.debug("C (_load_data)  backend_info_list: %s", self._backend_info_by_backend)
        # self.logging.debug("C (_load_data)  house_info_list: %s", HouseModel.info_by_id)
        # self.logging.debug("C (_load_data)  lobby_info_by_id: %s", LobbyModel.info_by_id)
        # self.logging.debug("C (_load_data)  room_info_by_id: %s", RoomModel.info_by_id)
        # self.logging.debug("C (_load_data)  game_config_by_type: %s", GameConfigModel.info_by_id)

    def get_backend_info(self, backend=None):
        value = object_util.get_info_by_id(self._backend_info_by_backend, backend)
        if not value:
            self.logging.warning("C WARNING! (get_backend_info) There is no backend_info in backends.json for "
                                 "backend: %s", backend)
        return value

    # Utility

    def _load_json(self, json_path):
        if not json_path:
            return None

        try:
            file = open(json_path)
            result = json.load(file)
            file.close()
        except Exception as error:
            result = None
            self.logging.error("Error while loading JSON by path: %s error: %s", json_path, error)
        return result
