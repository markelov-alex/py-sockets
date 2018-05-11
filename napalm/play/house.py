import json
import logging as _logging
import os
from threading import RLock

from napalm.core import ExportableMixIn, ReloadableModel
from napalm.play.protocol import MessageType
from napalm.socket.protocol import Protocol
from napalm.utils import default_logging_setup

# Log
# Temp
default_logging_setup()

# Log
# logging = _logging.getLogger("HOUSE")
# logging.level = _logging.DEBUG


# User

class Player(ExportableMixIn):
    """
    - Current player state
    - Proxy to user data
    - Contains protocol (connection to client)
    """

    logging = None

    @property
    def is_connected(self):
        # Used to muck cards on turn went to disconnected player and to kick off on new play started
        return self.protocol and self.protocol.is_ready

    # Proxy to user (for export_public_data())

    @property
    def user_id(self):
        return self.user.user_id if self.user else ""

    @property
    def social_id(self):
        return self.user.social_id if self.user else ""

    @property
    def first_name(self):
        return self.user.first_name if self.user else ""

    @property
    def last_name(self):
        return self.user.last_name if self.user else ""

    @property
    def image_url(self):
        return self.user.image_url if self.user else ""

    @property
    def image_url_small(self):
        return self.user.image_url_small if self.user else ""

    @property
    def image_url_normal(self):
        return self.user.image_url_normal if self.user else ""

    @property
    def level(self):
        return self.user.level if self.user else ""

    @property
    def money_amount(self):
        # Money available to take into game
        return self.user.money_amount if self.user else ""

    @property
    def total_money_amount(self):
        # Use this as money_amount when displaying in client's top panel (as it is in ZyngaPoker and others)
        return self.user.total_money_amount if self.user else ""

    @property
    def is_in_game(self):
        return self.user.is_in_game if self.user else ""

    @property
    def join_date(self):
        return self.user.join_date if self.user else ""

    @property
    def vip_days_available(self):
        return self.user.vip_days_available if self.user else ""

    @property
    def _property_names(self):
        # To save state
        return ["session_id", "lobby_id", "room_id", "place_index", "is_playing", "is_sit_out",
                "money_in_play", "gift_image_url"]

    @property
    def _public_property_names(self):
        # Always sync changes in client's code!
        return ["user_id", "social_id", "first_name", "last_name",
                "image_url", "image_url_small", "image_url_normal",
                "level", "money_amount", "money_in_play", "is_in_game",
                "join_date", "gift_image_url", "vip_days_available",
                "is_playing", "is_sit_out"]

    def __init__(self, house_config=None, session_id=-1, protocol=None):
        self.logging = _logging.getLogger("PLAYER")

        self.house_config = house_config
        self.session_id = session_id
        self.protocol = protocol or Protocol.dummy_protocol

        self.house = None
        self.lobby = None
        self.room = None
        self.game = None
        self.user = None

        self.is_guest = False
        # Used only on export/import (Set automatically on export)
        self.lobby_id = None
        self.room_id = None
        # (use place_index instead)
        # self.is_in_game = 0
        # Index of player's place in the play
        self.place_index = -1
        self.is_playing = False
        self.is_sit_out = False

        self.money_in_play = 0
        self.gift_image_url = ""

        self.is_just_restored = False
        self.missed_turns_count = 0
        self.missed_games_count = 0

        super().__init__()

    def dispose(self):
        self.remove_money_in_play()

        # on_player_dispose = self.on_player_dispose
        # if on_player_dispose:
        #     self.on_player_dispose = None
        #     # (Dispose from lobby and user_manager)
        #     on_player_dispose(self)
        #     return

        self.logging.debug("U temp (dispose) protocol: %s", self.protocol)

        if self.house:
            self.house.remove_player(self)
        if self.lobby:
            self.lobby.remove_player(self)
        if self.room:
            self.room.remove_player(self)
        if self.user:
            self.user.remove_player(self)

        self.house = None
        self.lobby = None
        self.room = None
        self.game = None
        self.user = None

        self.house_config = None
        # (To clear ref on dummy after detach_protocol())
        self.protocol = None

        # try to reset all properties
        self.__init__()

        self.lobby_id = None
        self.room_id = None
        self.place_index = -1
        self.is_playing = False

        self.logging = None

    def __repr__(self):
        session_id_suffix = "(" + str(self.session_id) + ")" if self.session_id >= 0 else ""
        return "<{0} user_id:{1} protocol_id:{2} name:{3} place_index:{4}>". \
            format(self.__class__.__name__, self.user_id + session_id_suffix,
                   self.protocol.protocol_id if self.protocol else "",
                   self.first_name + (" " + self.last_name if self.last_name else ""), self.place_index)

    def export_data(self):
        self.lobby_id = self.lobby.lobby_id if self.lobby else None
        self.room_id = self.room.room_id if self.room else None
        # self.is_in_game = bool(self.game)
        return super().export_data()

    # Override
    def reset_game_state(self):
        # Reset state properties for current game
        pass

    def update_self_user_info(self):
        if self.protocol:
            self.protocol.update_self_user_info(self.user.export_public_data())

    def add_money_in_play(self, amount=0):
        # self.logging.debug("temp(_add_money_in_play)", "player:", player, "amount:", amount,
        # "player.money_amount:", player.money_amount, "player.money_in_play:", player.money_in_play)
        # (Check money_in_play>0 for restoring after server restart: player.money_in_play already set)
        if self.room and self.room.game and amount > 0:
            min_buy_in = self.room.room_model.min_buy_in
            max_buy_in = self.room.room_model.max_buy_in
            amount = min(max_buy_in - self.money_in_play, amount)

            if amount > 0:
                amount = self.user.take_money(amount, min_buy_in)
                self.money_in_play += amount

            self.update_self_user_info()

            self.logging.debug("  temp(_add_money_in_play) player: %s amount: %s player.money_amount: %s "
                               "player.money_in_play: %s", self, amount, self.money_amount, self.money_in_play)

    def remove_money_in_play(self):
        if self.money_in_play:
            amount = self.user.put_money_back(self.money_in_play)
            self.money_in_play -= amount
            self.update_self_user_info()


class PlayerManager:
    lock = RLock()
    logging = None

    # Save/Restore

    @property
    def players_data(self):
        player_info_list = []
        is_restore_player_in_room = self.house_config.house_model.is_restore_player_in_room
        for player in self.player_set:
            if player.game or (player.room and is_restore_player_in_room):
                player_info_list.append(player.export_data())
        return player_info_list

    @players_data.setter
    def players_data(self, value):
        if value is None:
            return

        player_info_list = value
        if player_info_list:
            for player_info in player_info_list:
                player = self.house_config.player_class(self.house_config)
                # (Will set up also session_id)
                player.import_data(player_info)
                self.add_player(player)

    def __init__(self, house_config=None) -> None:
        super().__init__()

        self.house_config = house_config
        self.house_model = house_config.house_model if house_config else None

        self.player_set = set()
        self.player_by_session_id = dict()
        self.disconnected_player_by_session_id = dict()
        self.max_session_id = None

    def dispose(self):
        for player in self.player_set:
            # (To avoid calling user.remove_player())
            player.user = None
            player.dispose()
        self.player_set.clear()
        self.player_by_session_id.clear()
        self.disconnected_player_by_session_id.clear()

        self.house_config = None
        self.house_model = None

    # Player

    def on_connect(self, protocol=None, session_id=-1):
        # Get or create

        # Try reconnect
        with self.lock:
            if protocol:
                if session_id < 0:
                    # (Note: return the last disconnected as it has the best chances that restoring game not
                    # finished or kicked him out)
                    player = self.disconnected_player_by_session_id.popitem()[1] \
                        if len(self.disconnected_player_by_session_id) else None
                else:
                    player = self.disconnected_player_by_session_id[session_id] \
                        if session_id in self.disconnected_player_by_session_id else None
                if player:
                    # player.is_just_restored = True
                    player.protocol = protocol
                    return player

        # if self.house_model.is_allow_multiple_connection_to_player and \
        #         session_id >= 0 and session_id in self.player_by_session_id:
        #     return self.player_by_session_id[session_id]

        # Create new
        player = self.house_config.player_class(self.house_config, session_id, protocol)
        # (Will take care of session_id)
        self.add_player(player)

        return player

    def on_disconnect(self, player):
        if player:
            session_id = player.session_id if player else None
            if session_id in self.disconnected_player_by_session_id:
                self.logging.error("Disconnected player is already among disconnected ones! "
                                   "user_id: %s session_id: %s", player.user_id, session_id)
            self.disconnected_player_by_session_id[session_id] = player

    # def get_player_by_session_id(self, session_id=-1):
    #     if session_id < 0 and len(self.player_by_session_id):
    #         return next(iter(self.player_by_session_id.values()))
    #     return self.player_by_session_id[session_id] if session_id in self.player_by_session_id else None

    def add_player(self, player):
        self.player_set.add(player)
        player.user = self

        # todo check session_id int/str
        session_id = player.session_id if player.session_id >= 0 else 0
        while session_id in self.player_by_session_id and self.player_by_session_id[session_id] != player:
            session_id += 1
        player.session_id = session_id
        # if session_id in self.player_by_session_id and self.player_by_session_id[session_id] != player:
        #     self.logging.error("Overwriting player instance with same session_id: %s in user. "
        #                        "user_id: %s social_id: %", player.session_id, player.user_id, player.social_id)

        self.player_by_session_id[session_id] = player

        if not player.protocol or player.protocol == Protocol.dummy_protocol:
            self.on_disconnect(player)

    def remove_player(self, player):
        # (Still no guarantee: lock before condition which decides to call remove_player())
        with self.lock:
            if player in self.player_set:
                self.player_set.remove(player)
            session_id = player.session_id if player else None
            if session_id in self.player_by_session_id:
                del self.player_by_session_id[session_id]
            if session_id in self.disconnected_player_by_session_id:
                del self.disconnected_player_by_session_id[session_id]
            player.user = None

            if len(self.player_set) == 0:
                self.dispose()


class User(PlayerManager, ExportableMixIn):
    """
    - Current user data
    - Connection to back-end (through service)
    - Managing players
    """

    logging = None

    @property
    def total_money_amount(self):
        total_money_in_play = 0
        for player in self.player_set:
            total_money_in_play += player.money_in_play
        return self.money_amount + total_money_in_play

    @property
    def _property_names(self):
        return ["user_id", "social_id", "first_name", "last_name",
                "image_url", "image_url_small", "image_url_normal",
                "level", "money_amount", "is_in_game",
                "join_date", "vip_days_available",
                # For save/restore
                "players_data"]

    def __init__(self, house_config=None, user_id="", social_id=""):  # , access_token="", auth_sig="", backend_info=None):
        self.logging = _logging.getLogger("USER")

        super().__init__()
        PlayerManager.__init__(self, house_config)

        # if not house_config:
        #     return
        #
        # self._service = house_config.service_class()  # social_id, access_token, auth_sig, backend_info)
        # # if not self._service.check_auth_sig():
        # #     return

        self.house_config = house_config
        self.house_model = house_config.house_model if house_config else None
        # Credentials for php server (user_id is social_id indeed)
        self.user_id = user_id
        self.social_id = social_id
        # self.access_token = access_token
        # self.auth_sig = auth_sig

        self.house = None
        self._service = house_config.service_class() if house_config else None

        # todo move to user
        self.first_name = ""
        self.last_name = ""
        self.image_url = ""
        self.image_url_small = ""
        self.image_url_normal = ""
        self.level = -1
        self.money_amount = 0
        # (Needed if can play on several servers at same time)
        self.is_in_game = 0
        self.join_date = ""
        self.vip_days_available = -1

        # (Shouldn't be called on restore)
        # self.update_self_user_info()
        # user_info = self._service.getCurrentUserFullInfo()
        # # user_info = [user_id, "Name " + user_id.capitalize() + "", "", "", "", "", -1, 5000, 0, 0, "", "", -1]
        # # if user_info[0] != user_id:
        # #     self.logging.error("L WARNING! user_id mismatch! "
        # #                          "user_id from client: %s user_id from php server: %s", user_id, user_info[0])
        # #     return
        # self.import_data(user_info)

    def dispose(self):
        # Move back all money_in_play for all players and save that on server
        self.remove_all_money_in_play()

        if self.house:
            self.house.remove_user(self)
            self.house = None

        PlayerManager.dispose(self)

        self.house_config = None
        self.house_model = None
        self.logging = None

        self.user_id = None
        self.social_id = None
        # self.access_token = None
        # self.auth_sig = None

        if self._service:
            self._service.dispose()
            self._service = None

        # try to reset all properties
        self.__init__()

    def __repr__(self):
        return "<{0} user_id:{1}>".format(self.__class__.__name__, self.user_id)

    # Protocol

    # def send_message(self, message_type, text, sender):
    #     if message_type and text and sender:
    #         for player in self.player_set:
    #             player.protocol.send_message(message_type, text, sender, self)

    # Service

    def check_credentials(self, social_id, access_token, auth_sig, backend=None):
        if not social_id or not access_token or not auth_sig:
            return False

        if not self.social_id:
            self.social_id = social_id
        elif self.social_id != social_id:
            return False

        backend_info = self.house_model.get_backend_info(backend)
        return self._service.check_auth_sig(social_id, access_token, auth_sig, backend_info)

    def remove_all_money_in_play(self):
        amount = 0
        # Remove from players
        for player in self.player_set:
            if player.money_in_play:
                amount += player.money_in_play
                player.money_in_play = 0
        # Add back to user
        if amount:
            result = self._service.increase(amount)
            amount = result["money"] if "money" in result else 0
            self.money_amount += amount
        return amount

    def take_money(self, amount, min_amount):
        if self.money_amount < min_amount or self.money_amount <= 0:
            return 0
        amount = min(amount, self.money_amount)

        result = self._service.decrease(money=amount)
        amount = result["money"] if "money" in result else 0

        self.money_amount -= amount

        return amount

    def put_money_back(self, amount):
        if amount <= 0:
            return 0

        result = self._service.increase(money=amount)
        amount = result["money"] if "money" in result else 0

        self.money_amount += amount
        return amount

    def update_self_user_info(self):
        # (Note: If there is only one socket-server an user could connect to, we don't need
        # to ask backend for user info more than once, on first connect)
        # todo prevent frequent calling
        user_info = self._service.getCurrentUserFullInfo()
        self.import_data(user_info)

        for player in self.player_set:
            player.update_self_user_info()

    def gameEnd(self, winners_data, loser_ids, shootout=False, sitngo=False):
        self._service.gameEnd(winners_data, loser_ids, shootout, sitngo)


# House

class UserManager:
    """
    session_id = 0, 1, ..., N;  -1 or None will be considered as default: 0
    Used to restore multisession games of user.
    # todo rename session_id to slot_index or session_slot - if it has no more
    #     need than not to shuffle games on multisession clients when reconnecting
    #     (where you can load several games into single client app.)
    # for now, maybe temporarily we remove session_id
    """

    logging = None
    house_model = None

    @property
    def users_online(self):
        # Just for statistics (to know how many users play multisession)
        return len(self._user_by_id)

    @property
    def players_online(self):
        # return len(self._player_set)
        return sum([len(user.player_set) for user in self._user_by_id])

    @property
    def players_connected(self):
        # For statistics
        # return len(self._player_set) - len(self._disconnected_player_set)
        return sum([len(user.player_set) - len(user.disconnected_player_set) for user in self._user_by_id])

    # Save/Restore

    @property
    def users_data(self):
        return {user.user_id: user.export_data() for user in self._user_by_id.values()
                if len(user.player_set) or self.house_model.is_save_all_users}

    @users_data.setter
    def users_data(self, value):
        if value is None:
            return
        for user_id, user_info in value.items():
            user = self._retrieve_user(user_id)
            user.import_data(user_info)
            self._add_user(user)
        self._update_players_online()

    def __init__(self, house_config):
        # Model
        self.house_config = house_config
        """:type: HouseConfig"""

        if not Protocol.dummy_protocol and self.house_config.protocol_class:
            Protocol.dummy_protocol = self.house_config.protocol_class()

        self._user_by_id = {}

        # State
        self._is_restoring_now = False

    def dispose(self):
        for user in self._user_by_id.values():
            user.dispose()
        self._user_by_id.clear()

        self._is_restoring_now = False

        # Model
        self.house_config = None

    def __repr__(self):
        return "<{0} house_id:{1} user_count:{2}>".format(
            self.__class__.__name__, self.house_model.house_id, self.users_online)

    def on_player_connected(self, protocol, user_id, social_id=None, access_token=None, auth_sig=None,
                            backend=None, session_id=-1):
        """
        :param user_id:
        :param social_id:
        :param access_token:
        :param auth_sig:
        :param backend:
        :param session_id: connect to this session if disconnected or not yet connected, or choose another if busy
        Convenient for multiplayer clients, where client's screen divided for each player: session_id helps not to
        mash up the screen order on reconnect.
        :param protocol:
        :return:
        """

        user = self._retrieve_user(user_id)
        if not user.check_credentials(social_id, access_token, auth_sig, backend):
            return None
        self._add_user(user)

        player = user.on_connect(protocol, session_id)

        self._update_players_online()

        return player

    def on_player_disconnected(self, player):
        # self.logging.debug("L -temp LOBBY_REMOVING_USER (on_player_disconnected) player_set: %s player: %s "
        #                    "is_continue_on_disconnect: %s and ("
        #                    # "player_reconnect_timeout_sec: " + self.house_model.player_reconnect_timeout_sec + " or"
        #                    "player.play: %s)", self._player_set,  # [player for player in self._player_set],
        #                    player, self.house_model.is_continue_on_disconnect, player.game)
        # (Note: We can dispose disconnected players later only on timeout or when the player looses the play)
        if self.house_model.is_continue_on_disconnect and (
                # self.house_model.player_reconnect_timeout_sec > 0 or
                player.game):
            player.user.on_disconnect(player)
        else:
            player.dispose()

        self._update_players_online()

    def _retrieve_user(self, user_id):
        user = self._user_by_id[user_id] if user_id in self._user_by_id else None
        if not user:
            user = self.house_model.user_class(self.house_config, user_id)

            # Get user info from backend on new user just connected
            if not self._is_restoring_now:
                user.update_self_user_info()
        return user

    def get_user(self, user_id):
        return self._user_by_id[user_id] if user_id in self._user_by_id else None

    def _add_user(self, user):
        # (Theoretically)
        if user.house and user.house != self:
            user.house.remove_user(user)

        user.house = self
        self._user_by_id[user.user_id] = user

        # Only on restoring, player_set could be not null
        for player in user.player_set:
            self.goto_lobby(player)

    def remove_user(self, user):
        if user.user_id in self._user_by_id:
            del self._user_by_id[user.user_id]
            user.house = None

    def _update_players_online(self):
        self.house_model.players_online = self.players_online


class LobbyManager:
    logging = None

    # Save/Restore

    @property
    def lobbies_data(self):
        return {lobby.lobby_id: lobby.export_data() for lobby in self._lobby_list}

    @lobbies_data.setter
    def lobbies_data(self, value):
        if value is None:
            return
        for lobby_id, lobby_info in value.items():
            lobby = self._lobby_by_id[lobby_id] if lobby_id in self._lobby_by_id else None
            if not lobby:
                self.logging.error("Error while restoring lobbies! There is no lobby with id: %s", lobby_id)
                continue
            lobby.import_data(lobby_info)

    def __init__(self, house_config) -> None:
        super().__init__(house_config)
        self.house_config = house_config
        self.house_model = house_config.house_model

        self._lobby_list = []
        self._lobby_by_id = {}
        lobby_class = self.house_config.lobby_class
        for lobby_model in self.house_model.lobby_model_list:
            # Create
            lobby = lobby_class(self, lobby_model)
            self._lobby_list.append(lobby)
            self._lobby_by_id[lobby.lobby_id] = lobby

    def dispose(self):
        for lobby in self._lobby_list:
            # Dispose
            lobby.dispose()
        self._lobby_list.clear()
        self._lobby_by_id.clear()

        self.house_config = None
        self.house_model = None

    # Protocol process methods (Lobby)

    def goto_lobby(self, player, lobby_id=-1):
        # Use default
        if lobby_id < 0:
            if player.lobby:
                return
            lobby_id = player.lobby_id if player.lobby_id >= 0 else self.house_model.default_lobby_id

        # Get lobby instance
        if lobby_id < 0:
            lobby = self.choose_default_lobby(player)
        else:
            if lobby_id not in self._lobby_by_id:
                self.logging.error("Try to go to lobby %s which does not exist! lobby_ids: %s",
                                   lobby_id, self._lobby_by_id.keys())
                return
            lobby = self._lobby_by_id[lobby_id]

        # Add
        lobby.add_player(player)

        # todo? restore in room and game if player is just restored

    def choose_default_lobby(self, player):
        # Choose appropriate lobby for player concerning his money available or lobbies load
        return self._lobby_list[0]

    def get_lobby_info_list(self, player):
        self.logging.debug("L (get_lobby_info_list) house_id: %s lobby_info_list: %s",
                           self.house_model.house_id, self.house_model.lobby_info_list)

        lobby_info_list = [lobby.lobby_model.export_public_data() for lobby in self._lobby_list]
        # lobby_info_list = [lobby.lobby_model.export_public_data()
        # for lobby in self._lobby_list if not lobby.is_paused]
        player.protocol.lobby_info_list(self.house_model.house_id, lobby_info_list)

    def send_message(self, message_type, text, sender_player, receiver_id=-1, is_check_security=False):
        # is_check_security - to check params received from network to avoid spamming
        if not message_type or not text or not sender_player:
            return

        # Mail messages (through php server, receiver should react on it: read, accept, delete, etc)
        if message_type == MessageType.MSG_TYPE_MAIL:
            if is_check_security:
                # todo check either receiver is a friend of sender (security)
                pass
            # todo save mail in php server & send response from server to player if online
            # ??--todo broadcast somehow to all player sessions of current user (?) -
            # todo broadcast to all sessions if message is read to avoid forcing
            #   the user to read same message in all sessions
            # all browser tabs/devices should receive the message (?)
            pass
            return

        # Public, chat (broadcast) and private (personal) messages
        if sender_player.room:
            # In the room
            sender_player.room.send_message(message_type, text, sender_player, receiver_id)
        elif sender_player.lobby:
            # In the lobby
            sender_player.lobby.send_message(message_type, text, sender_player, receiver_id)
        else:
            self.logging.error("[That should not happen] "
                               "Player should be in a room or in lobby to be able to send message! "
                               "message_type: %s sender_player: %s", message_type, sender_player)
            # self.logging.warning("WARNING! (send_message) Wrong message_type: %s sender_user: %s "
            # "text: %s receiver_index: %s", message_type, sender_user, text, receiver_index)


class SaveLoadHouseStateMixIn(ExportableMixIn):
    logging = None
    house_model = None

    _user_by_id = None

    # todo adopt for real circumstances (on x changes or on each y minute)
    def try_save_house_state_on_change(self):
        if self.house_model.is_save_house_state_on_any_change and not self._is_restoring_now:
            self.save_house_state()

    def save_house_state(self):
        if not self.house_model.is_save_house_state_enabled:
            self.logging.info("L (save_house_state) Saving disabled. "
                              "house_model.is_save_house_state_enabled: %s %s",
                              self.house_model.is_save_house_state_enabled, self)
            return

        self.logging.debug("L =(SAVE_lobby_state) Start %s", self)
        self._save_state(self.house_model.house_name, self.export_data())
        self.logging.debug("=(save_house_state) End %s", self)

    def restore_house_state(self):
        if not self.house_model.is_save_house_state_enabled or not self.house_model.is_restore_house_state_on_start:
            self.logging.info("L (restore_house_state) Saving and restoring disabled. "
                              "house_model.is_save_house_state_enabled: %s "
                              "house_model.is_restore_house_state_on_start: %s %s",
                              self.house_model.is_save_house_state_enabled,
                              self.house_model.is_restore_house_state_on_start, self)
            return

        self._is_restoring_now = True
        house_data = self._load_state(self.house_model.house_name)
        if house_data:
            self.import_data(house_data)
            self.logging.debug("L =(restore_house_state) End %s", self)

        self._is_restoring_now = False

    # todo use also memcached instead of saving to file all the time
    # Override
    def _save_state(self, name, state_json):
        filename = "dumps/" + name + "_state_dump.json"
        dir_name = os.path.dirname(filename)
        if dir_name and not os.path.exists(dir_name):
            os.makedirs(dir_name)
        json.dump(state_json, open(filename, "w"))

    # todo use also memcached instead of saving to file all the time
    # Override
    def _load_state(self, name):
        filename = "dumps/" + name + "_state_dump.json"
        if not os.path.exists(filename):
            self.logging.warning("L (_load_state) There is no json file with lobby state data. "
                                 "filename: %s", filename, self)
            return None
        return json.load(open(filename))


class House(LobbyManager, UserManager, SaveLoadHouseStateMixIn):
    logging = None

    _is_paused = False

    @property
    def is_paused(self):
        """Used in protocol - don't process any command if paused"""
        return self._is_paused

    # Save/Restore

    @property
    def _property_names(self):
        # Note: the order is very important!
        return ["model_data", "lobbies_data", "users_data"]

    @property
    def model_data(self):
        return self.house_model.export_data()

    @model_data.setter
    def model_data(self, value):
        if value is None:
            return
        self.house_model.import_data(value)
        # (For restoring)
        self.house_model.apply_changes()

    def __init__(self, house_config):
        self.house_config = house_config
        """:type: HouseConfig"""
        self.house_model = house_config.house_model

        self.logging = _logging.getLogger("HOUSE")
        self.logging.debug("L Create House %s", self.house_model.house_id)  # , self.house_model.room_info_list)

        SaveLoadHouseStateMixIn.__init__(self)
        LobbyManager.__init__(self, house_config)
        UserManager.__init__(self, house_config)

    def dispose(self):
        UserManager.dispose(self)
        LobbyManager.dispose(self)

        self.house_config = None
        self.house_model = None

        self.logging = None

    def __repr__(self):
        return "<{0} id:{1} name:{2} lobby_count:{3} user_count:{4}>".format(
            self.__class__.__name__, self.house_model.house_id, self.house_model.house_name,
            len(self._lobby_by_id), self.users_online)

    def start(self):
        if self.house_model.is_restore_house_state_on_start:
            self.restore_house_state()
            self.resume()

    def pause(self):
        """Can be used to save current state correctly if want to restart server
        just after that"""
        self._is_paused = True
        for lobby in self._lobby_list:
            lobby.pause()

    def resume(self):
        """Used to resume games after server state restored. Initially, all that
        pause-resume in house and lobby were started to resume games on server start"""
        self._is_paused = False
        for lobby in self._lobby_list:
            lobby.resume()

    def stop(self):
        pass


class HouseModel(ReloadableModel):
    id_name = "house_id"
    # (HouseModel shouldn't know about LobbyModel, so we use reference on LobbyModel)
    lobby_model_class = None
    game_config_model_class = None

    lobby_model_list = None
    lobby_model_by_id = None

    @property
    def _config_property_names(self):
        return ["house_id", "house_name", "host", "port", "lobbies", "default_lobby_id", "is_allow_guest_auth",
                "is_allow_multisession", "is_allow_multisession_in_the_room", "is_save_house_state_enabled",
                "is_save_house_state_on_any_change", "is_restore_house_state_on_start", "is_continue_on_disconnect"]

    @property
    def _public_property_names(self):
        return ["house_id", "house_name", "host", "port", "players_online"]

    def __init__(self, initial_config=None):
        # Default config values
        self.house_id = None
        self.house_name = None
        self.host = None
        self.port = None
        self.lobbies = None
        # -1 for choosing appropriate lobby automatically
        self.default_lobby_id = -1
        # Allow user to play without authorizing
        self.is_allow_guest_auth = True
        # Allow playing from same user account on current server from multiscreen client,
        # multiple devices or multiple browser tabs
        self.is_allow_multisession = True
        # Control same player from different clients (not depending on is_allow_multisession)
        # (for this the player instance should process multiple protocols)
        # self.is_allow_multiple_connection_to_player = False
        # Allow playing from same user account in same room (allow user playing with himself)
        self.is_allow_multisession_in_the_room = False
        # -self.is_allow_same_user_in_the_room = False

        # Allow to restore and continue all games after server restart or some failure
        self.is_send_each_player_joined_the_room = False
        self.is_save_house_state_enabled = True
        self.is_save_house_state_on_exit = True
        # (Don't use this in release version if lobby saves state to file)
        self.is_save_house_state_on_any_change = True
        self.is_restore_house_state_on_start = True
        # (If False, only if player in the game)
        self.is_restore_player_in_room = True
        # (Save all users to avoid mass get_user_info requests to php-server on socket server restart)
        self.is_save_all_users = True
        # (Allow to continue play on client reconnect: Don't dispose user instance immediately on disconnect)
        self.is_continue_on_disconnect = True
        # Player will be disposed on timeout. Set 0 to disable timeout
        # self.player_reconnect_timeout_sec = 0
        self.is_rooms_creation_enabled = True
        # (See "Business Tour" https://minigames.mail.ru/monopolia)
        self.is_public_rooms_creation_enabled = True
        # Notify all players in the room when someone joins or leave the room (in most games it's not needed)
        self.is_notify_each_player_joined_the_room = False

        self.lobby_model_list = []
        self.lobby_model_by_id = {}
        self.game_config_by_type = {}

        super().__init__(initial_config)

        # State
        self.players_online = 0

        self.logging = _logging.getLogger("HOUSE-MDL")

    def on_reload(self, new_initial_config=None):
        super().on_reload(new_initial_config)

        # Use all lobbies if not defined ids
        if not self.lobbies and self.lobby_model_class and self.lobby_model_class.model_by_id:
            self.lobbies = list(self.lobby_model_class.model_by_id.keys())

        ReloadableModel.update_model_list(self.lobby_model_list, self.lobby_model_by_id,
                                          self.lobbies, self.lobby_model_class, True)

        # Update default_lobby_id
        # (no need. -1 used to arrange players automatically)
        # if self.default_lobby_id < 0 or self.default_lobby_id not in self.lobby_model_by_id:
        #     self.default_lobby_id = self.lobby_model_list[0].lobby_id if len(self.lobby_model_list) else -1
        if str(self.default_lobby_id) != "-1" and self.default_lobby_id not in self.lobby_model_by_id:
            self.default_lobby_id = -1
