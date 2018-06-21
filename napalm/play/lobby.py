import logging

from napalm.core import ReloadableModel, ExportableMixIn
from napalm.play.game import GameConfigModel
from napalm.play.house import Player
from napalm.play.protocol import MessageCode, MessageType, RoomType, FindAndJoin, TournamentType
from napalm.socket.parser import CommandParser
from napalm.utils import object_util


# todo check goto_lobby also adds to room and game if room_id and place_index are set
# Room

class RoomModel(ReloadableModel):
    """
    - Just room info.

    Could be updated from file during the game. To apply loaded data call apply_changes().
    """

    # default_pot_limit = ""  # todo!?
    # (Loaded changes take effect only after apply_changes() called)
    is_change_on_command = True
    id_name = "room_id"

    @property
    def is_password_needed(self):
        return bool(self.room_password)

    @property
    def visitor_count(self):
        return self.total_player_count - self.playing_count

    @property
    def _config_property_names(self):
        return ["room_id", "room_name", "room_code", "game_params",
                "tournament_type", "max_tournament_game_count",
                "max_player_count", "max_visitor_count", "room_password", "owner_user_id",
                # Timing
                "waiting_for_other_players_countdown_sec", "start_game_countdown_sec",
                "resume_game_countdown_sec", "rebuying_sec",
                "apply_round_delay_sec", "round_timeout_sec", "between_rounds_delay_sec", "turn_timeout_sec",
                "game_timeout_sec", "show_game_winner_delay_sec", "show_tournament_winner_max_delay_sec",
                "is_reset_round_timer_on_restore", "is_reset_turn_timer_on_restore"]

    @property
    def _public_property_names(self):
        return ["room_id", "room_name", "room_code", "game_params",
                "tournament_type", "max_tournament_game_count",
                "max_player_count", "max_visitor_count", "is_password_needed",
                "playing_count", "visitor_count",
                # (Placed here to avoid creating new model classes)
                "turn_timeout_sec", "between_rounds_delay_sec"]

    @property
    def _game_property_name_list(self):
        """
        Rule 1: keep order same as in json config file (lobbies.json)
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return ["min_stake", "max_stake", "min_buy_in", "max_buy_in"]

    _room_code = None

    @property
    def room_code(self):
        # return self._room_code
        return CommandParser.make_room_code(self.game_id, self.game_variation, self.game_type, self.room_type)

    @room_code.setter
    def room_code(self, value):
        self._room_code = value
        # Parse room_code
        self.game_id, self.game_variation, self.game_type, self.room_type = \
            CommandParser.parse_room_code(self._room_code)

    @property
    def game_config_ids(self):
        # (Note: in games.json game_variation could be nested inside game_id and game_type inside- game_variation)
        return [str(self.game_id), str(self.game_variation), str(self.game_type)]

    @property
    def is_public(self):
        return self.room_type == RoomType.PUBLIC

    @property
    def is_vip(self):
        return self.room_type == RoomType.VIP

    @property
    def is_private(self):
        return self.room_type == RoomType.PRIVATE

    # _game_params = None

    @property
    def game_params(self):
        # return self._game_params
        return object_util.object_to_plain_list(self, self._game_property_name_list)

    @game_params.setter
    def game_params(self, value):
        # self._game_params = value
        object_util.set_up_object(self, value, self._game_property_name_list)

    @property
    def is_tournament(self):
        return self.tournament_type != TournamentType.NONE

    def __init__(self, initial_config=None):
        self.game_config_model = None

        # Set default config values
        self.room_id = ""
        self.room_name = ""
        self.room_code = ""
        # (Temp var to export and import game_param vars)
        self.game_params = []
        self.tournament_type = TournamentType.NONE
        self.max_tournament_game_count = -1
        #  -1 - unbounded
        self.max_player_count = -1
        self.max_visitor_count = -1
        # for private rooms
        self.room_password = ""

        # "" - for public, checked before returning room info list to specified player
        # (for some games only owners can see their rooms (is_private==True))
        self.owner_user_id = ""

        # room_code parsed
        self.game_id = None
        self.game_variation = None
        self.game_type = None
        self.room_type = None

        # game_params parsed
        # Small and big blind stake for poker
        self.min_stake = 0
        self.max_stake = 0
        # Min and max money_in_play that player can join the game
        self.min_buy_in = 0
        self.max_buy_in = 0

        # Timing
        self.waiting_for_other_players_countdown_sec = 0  # (0 for Poker, 15 for Monopoly)
        self.start_game_countdown_sec = 0  # (0 for Poker, 3 for Monopoly)
        self.resume_game_countdown_sec = 3
        self.rebuying_sec = 30  # Hold place while rebuying for rebuying_sec
        self.apply_round_delay_sec = .5  # Time interval between new round start and turn moved to player
        self.round_timeout_sec = -1
        self.between_rounds_delay_sec = .5
        self.turn_timeout_sec = 10
        self.game_timeout_sec = -1
        self.show_game_winner_delay_sec = 1
        self.show_tournament_winner_max_delay_sec = 60
        self.is_reset_round_timer_on_restore = False
        self.is_reset_turn_timer_on_restore = True

        self.is_clear_room_on_end_tournament = False
        self.is_clear_game_on_end_tournament = False

        # State
        self.total_player_count = 0
        self.playing_count = 0
        self.tournament_game_count = 0
        # -self.visitor_count = 0

        # Set up
        super().__init__(initial_config)

        self.logging = logging.getLogger("ROOM-MDL")

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_code:{3} max_players:{4}>".format(
            self.__class__.__name__, self.room_id, self.room_name, self.room_code, self.max_player_count)

    def dispose(self):
        if self.game_config_model:
            self.game_config_model.dispose()
            self.game_config_model = None

        super().dispose()

    def _apply_initial_config(self):
        super()._apply_initial_config()

        if not self.game_config_model:
            self.game_config_model = GameConfigModel.create_multimodel_by_ids(self.game_config_ids)
        else:
            self.game_config_model.ids = self.game_config_ids

    def apply_changes(self):
        super().apply_changes()

        if not self.game_config_model:
            self.game_config_model = GameConfigModel.create_multimodel_by_ids(self.game_config_ids)
        else:
            self.game_config_model.ids = self.game_config_ids


class RoomSendMixIn:
    """
    - Protocol send methods (Room and Game)
    """
    player_set = None
    logging = None

    # Room

    def send_player_joined_the_room(self, joined_player, exclude_players=None):
        for player in self.player_set:
            if exclude_players and player not in exclude_players:
                protocol = player.protocol
                self.logging.debug("R (send_player_joined_the_room) %s %s", player, player.protocol)
                """:type : GameProtocol"""
                protocol.player_joined_the_room(joined_player.export_public_data())

    def send_player_joined_the_game(self, joined_player):  # , is_reconnect=False
        # if not is_reconnect:
        #     log_text = " ".join((joined_player.first_name, joined_player.last_name,
        #                         joined_player.user_id, "joined the play"))

        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.player_joined_the_game(joined_player.place_index, joined_player.export_public_data())  # , log_text

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
                protocol.player_left_the_room(left_player.export_public_data())

    def send_message(self, message_type, text, sender_player, receiver_id=-1):
        is_message_private = MessageType.is_message_private(message_type)
        for player in self.player_set:
            # if not is_message_private or receiver_id < 0 or player.user_id == receiver_id:
            if not is_message_private or player.user_id == receiver_id:
                player.protocol.send_message(message_type, text, sender_player, receiver_id)

    def send_log(self, log_text):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.send_log(log_text)

    # Game

    def send_ready_to_start(self, place_index, is_ready, start_game_countdown_sec):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.ready_to_start(place_index, is_ready, start_game_countdown_sec)

    def send_reset_game(self):
        for player in self.player_set:
            protocol = player.protocol
            """:type : GameProtocol"""
            protocol.reset_game()

    # todo add unittests
    def send_pause_game(self, is_paused, delay_sec=0):
        pass
        # todo
        # for player in self.player_set:
        #     protocol = player.protocol
        #     """:type : GameProtocol"""
        #     protocol.pause_game(is_paused, delay_sec)

    def send_change_player_turn(self, player_in_turn_index, turn_timeout_sec):
        self.logging.debug("R (send_change_player_turn)  room: %s", self)
        # todo move
        # if self.on_game_state_changed:
        #     self.logging.debug("R (send_change_player_turn) [try_save] room: %s", self)
        #     self.on_game_state_changed()

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

    # todo unittests
    def send_player_sit_out(self, place_index, value):
        for player in self.player_set:
            protocol = player.protocol
            """:type: PokerProtocol"""
            protocol.player_sit_out(place_index, value)


class Room(RoomSendMixIn, ExportableMixIn):
    logging = None

    @property
    def room_id(self):
        return self.room_model.room_id if self.room_model else None

    @property
    def has_free_seat_to_play(self):
        return self.room_model.max_player_count < 0 or not self.game or \
               len(self.game.player_list) < self.room_model.max_player_count

    @property
    def is_empty_room(self):
        # return self.room_model.max_player_count > 0 and (not self.game or not len(self.game.player_list))
        return not self.game or not len(self.game.player_list)

    # @property
    # def total_player_count(self):
    #     return len(self.player_set)
    #
    # @property
    # def playing_count(self):
    #     return len(self.game.player_list) if self.game else 0
    #
    # @property
    # def visitor_count(self):
    #     return self.total_player_count - self.playing_count

    # Save/Restore

    @property
    def _property_names(self):
        return ["model_data", "game_data"]

    @property
    def model_data(self):
        return self.room_model.export_data()

    @model_data.setter
    def model_data(self, value):
        if value is None:
            return
        self.room_model.import_data(value)
        # (For restoring)
        self.room_model.apply_changes()

    @property
    def game_data(self):
        return self.game.export_data() if self.game else None

    @game_data.setter
    def game_data(self, value):
        if value is None:
            return
        if not self.game:
            self._create_game()
        self.game.import_data(value)

    def __init__(self, house_config, room_model):
        super().__init__()  # ExportableMixIn.__init__(self)
        self.logging = logging.getLogger("ROOM")

        self.house_config = house_config
        self.house_model = house_config.house_model if house_config else None
        self.room_model = room_model

        # todo?
        self.lobby = None
        # Players added/removed
        self.player_set = set()  # type: set(Player)
        self.player_by_user_id = {}
        # Game created/disposed
        self.game = None
        """:type: Game"""

        self.on_game_state_changed = None

    def dispose(self):
        self.logging.debug("(dispose) %s", self)
        self._dispose_game()
        # Remove players after game disposed with correct finishing
        self.remove_all_players()

        if self.lobby:
            self.lobby.remove_room(self)
            self.lobby = None

        self.house_config = None
        self.house_model = None
        self.room_model = None

        self.on_game_state_changed = None

        # self.logging = None

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_code:{3} players:{4}/{5}>".format(
            self.__class__.__name__, self.room_model.room_id, self.room_model.room_name, self.room_model.room_code,
            self.room_model.playing_count, self.room_model.max_player_count)

    # Players

    def get_player(self, user_id):
        user_id = str(user_id)
        return self.player_by_user_id[user_id] if user_id in self.player_by_user_id else None

    # todo unittests
    def can_be_added_as_visitor(self, player):
        if not self.room_model or player not in self.player_set and \
                not self._check_can_be_added(player, self.room_model.room_password):
            return False

        return self.room_model.max_visitor_count < 0 or \
            len(self.room_model.visitor_count) < self.room_model.max_visitor_count

    # todo unittests
    def can_be_added_as_player(self, player, place_index=-1, money_in_play=0):
        """Needed to do not leave current room when trying to enter
        another one if cannot enter it with current params.
        Note: For some config, one can be added as a player but not as a visitor."""

        if not self.room_model or player not in self.player_set and \
                not self._check_can_be_added(player, self.room_model.room_password):
            return False

        return not self.game or self.game.can_be_added(player, place_index, money_in_play)

    def _check_can_be_added(self, player, password, is_message_enabled=True):
        # Avoid players entering same room from same account
        # (todo skip that kind of rooms from room list in lobby?)
        if not self.house_model.is_allow_multisession_in_the_room and player.user_id in self.player_by_user_id:
            self.logging.warning("R WARNING! (add_player) Player with same user_id is already added. player: %s "
                                 "user_id: %s self.player_set: %s is_allow_multisession: %s",
                                 player, player.user_id, self.player_set,
                                 self.house_model.is_allow_multisession_in_the_room)
            # self.logging.debug("temp (room.add_player) fail-same-auth-token-already-added %s", player)
            player.protocol.show_ok_message_dialog(MessageCode.JOIN_ROOM_FAIL_TITLE,
                                                   MessageCode.JOIN_ROOM_FAIL_SAME_USER)
            return False

        # Check password
        room_password = self.room_model.room_password
        if room_password and room_password != password:
            # self.logging.debug("temp (room.add_player) fail-password %s", player)
            self.logging.warning("R WARNING! (add_player) Wrong password. player: %s password: %s room_password: %s",
                                 player, password, room_password)
            # todo open enter-password-dialog which tries rejoin on ok and pause for 5 minutes after each 3 tries
            player.protocol.show_ok_message_dialog(MessageCode.JOIN_ROOM_FAIL_TITLE,
                                                   MessageCode.JOIN_ROOM_WRONG_PASSWORD)
            return False
        return True

    def add_player(self, player, password=None):
        """
        Add player or restore player added before.
        :param player:
        :param password:
        :return:
        """

        self.logging.debug("R (add_player) player: %s self.player_set: %s", player, self.player_set)
        # Restore session on client reconnect
        if player in self.player_set:
            self.logging.debug("R (add_player) Player is already added. Possibly restoring session. "
                               "player: %s player_set: %s", player, self.player_set)

            player.protocol.confirm_joined_the_room(self.room_model.export_public_data())
            if self.game:
                self.get_game_info(player, True)
            return True

        # ?- if player.room_id == self.room_id:
        #     password = self.room_model.room_password

        if not self._check_can_be_added(player, password):
            return False

        if player.room and player.room != self:
            player.room.remove_player(player)

        # Add
        player.room = self
        self.player_set.add(player)
        self.player_by_user_id[player.user_id] = player
        self.room_model.total_player_count += 1

        self.logging.debug("R temp self.player_set.add player: %s", player)
        if not self.game:
            self._create_game()

        # self.logging.debug("temp (room.add_player) Add %s", player)
        # (Check is_connected is to make server restoring faster)
        if player.is_connected:
            player.protocol.confirm_joined_the_room(self.room_model.export_public_data())

            if self.house_model.is_notify_each_player_joined_the_room:
                self.send_player_joined_the_room(player, [player])
            if self.game:
                self.get_game_info(player, True)

        return True

    def remove_player(self, player):
        # (Checking player.game only for performance optimization)
        self.logging.debug("R (remove_player) player: %s", player)
        if player in self.player_set:
            if player.game:
                self.leave_the_game(player)

            self.logging.debug("R  (remove_player) before-self.player_set: %s", self.player_set)
            # Remove
            self.player_set.remove(player)
            self.player_by_user_id.pop(player.user_id)
            player.room = None
            self.room_model.total_player_count -= 1

            # Send
            player.protocol.confirm_left_the_room()
            if self.house_model.is_notify_each_player_joined_the_room:
                self.send_player_left_the_room(player, [player])

            # self.logging.debug("temp (room.remove_player) ok %s player_set: %s", player, self.player_set)
            self.logging.debug("R   (remove_player)  after-self.player_set: %s", self.player_set)

            if not self.player_set:
                self._finish_game()
            return True
        self.logging.warning("R WARNING! (remove_player) Cannot remove player! Player not in "
                             "player_set: %s for player: %s", self.player_set, player)
        # self.logging.debug("temp (room.remove_player) fail-player-not-in-the-list %s player_set: %s",
        #  player, self.player_set)

        return False

    # ?
    # def make_all_players_leave(self):
    #     for player in self.player_set:
    #         player.lobby.goto

    def remove_all_players(self):
        # player_list = list(self.player_set)
        # (list() makes a copy of a set to enable remove items during iterating)
        for player in list(self.player_set):
            self.remove_player(player)

    # Game

    def check_and_apply_changes(self):
        # Can be applied only between games
        if (not self.game or not self.game.is_in_progress) and self.room_model.is_changed:
            # Apply
            self.room_model.apply_changes()
            # Inform about
            for player in self.player_set:
                self.lobby.get_room_info(player, self.room_id)

    def get_game_info(self, player, is_get_room_content=False):
        """
        :param player:
        :param is_get_room_content: can reset empty place while get_all_player_info() can't
        :return:
        """

        game_info = self.game.export_public_data_for(for_place_index=player.place_index) if self.game else None
        if is_get_room_content:
            player_info_list = [player.export_public_data() if player else None
                                for player in self.game.player_by_place_index_list] \
                if self.game else []
        else:
            player_info_list = None

        player.protocol.game_info(game_info, player_info_list)

    def join_the_game(self, player, place_index=-1, money_in_play=0):
        # (Player should be already added to the room)
        if player not in self.player_set:
            self.logging.warning("R WARNING! (join_the_game) Cannot join the play! Player not in player_set: %s "
                                 "for player: %s", self.player_set, player)
            return False

        result = self.game.add_player(player, place_index, money_in_play)
        return result

    def leave_the_game(self, player):
        if player not in self.player_set:
            self.logging.warning("R WARNING! (leave_the_game) Cannot leave the play! Player not in player_set: %s "
                                 "for player: %s", self.player_set, player)
            return False

        result = self.game.remove_player(player) if self.game else False
        return result

    def _create_game(self):
        if not self.game:
            # -todo ensure it's alright
            # todo unittests
            # self.room_model.apply_changes()
            # self.room_model.game_config_model.apply_changes()

            game_class = self.house_config.game_class
            self.game = game_class(self)

    def _finish_game(self):
        # check game wasn't finished before
        self._dispose_game()

    def _dispose_game(self):
        if self.game:
            self.game.dispose()
            self.game = None


# Lobby

class LobbyModel(ReloadableModel):
    room_model_list = None
    room_model_by_id = None

    id_name = "lobby_id"

    _available_room_models = None

    @property
    def available_room_models(self):
        if not self._available_room_models:
            self._available_room_models = [model for model in self.room_model_list if model.is_available]
        return self._available_room_models

    @property
    def _config_property_names(self):
        return ["lobby_id", "lobby_name", "rooms"]

    @property
    def _public_property_names(self):
        return ["lobby_id", "lobby_name", "rooms"]

    def __init__(self, initial_config=None):

        # Info params
        self.lobby_id = None
        self.lobby_name = ""
        self.rooms = None

        # Models
        self.room_model_list = []
        self.room_model_by_id = {}

        super().__init__(initial_config)

        self.logging = logging.getLogger("ROOM-MDL")

    def on_reload(self, new_initial_config=None):
        super().on_reload(new_initial_config)

        self._available_room_models = None

        ReloadableModel.update_model_list(self.room_model_list, self.room_model_by_id,
                                          self.rooms, RoomModel.model_class, True)


class RoomManager:
    logging = None

    # Save/Restore

    @property
    def rooms_data(self):
        return {room.room_id: room.export_data() for room in self.room_list}

    @rooms_data.setter
    def rooms_data(self, value):
        if value is None:
            return
        items = value.items() if isinstance(value, dict) else (enumerate(value) if isinstance(value, list) else None)
        for room_id, room_data in items:
            room = self.room_by_id[room_id] if room_id in self.room_by_id else self._create_room([room_id])
            room.import_data(room_data)

    def __init__(self, house, lobby_model):
        # Model
        self.house = house
        self.house_config = house.house_config
        """:type: HouseConfig"""
        self.lobby_model = lobby_model

        self.room_by_id = {}
        self.room_list = []

        # Create rooms
        for room_model in self.lobby_model.available_room_models:
            self._create_room(room_model)

    def dispose(self):
        # (list() needed to make a copy)
        for room in list(self.room_list):
            room.dispose()
        self.room_by_id = {}
        self.room_list = []

        # Model
        self.house_config = None
        self.lobby_model = None

    def __repr__(self):
        return "<{0} house_id:{1} room_count:{2}>".format(
            self.__class__.__name__, self.house_config.house_id, len(self.room_by_id))

    # List to be serialized
    def rooms_export_public_data(self, for_player=None):
        # todo consider private rooms for friends
        #  if is_show_for_friends then all user_ids of friends should be mentioned in room_model (?)
        self.logging.debug("L rooms_export_data room_by_id: %s room_list: %s", self.room_by_id, self.room_list)
        return [room.room_model.export_public_data() for room in self.room_list
                # Show private rooms only for owner
                if not room.room_model.is_private or
                (for_player and room.room_model.owner_user_id == for_player.user_id)]

    # Create/remove

    def _create_room(self, room_info_or_model, owner_player=None):
        if not room_info_or_model:
            self.logging.warning("L WARNING! (create_room) Empty argument! room_info_or_model: %s", room_info_or_model)
            return None

        # room_model
        room_model = self._create_room_model(room_info_or_model)
        room_model.owner_user_id = owner_player.user_id if owner_player else None
        self.logging.debug("L Create room room_model: %s", room_model)

        # room_id
        room_id = room_model.room_id if room_model else None
        if not room_id:
            self.logging.warning("L WARNING! (create_room) Empty room_id: %s in room_model: %s", room_id, room_model)
            return None
        if room_id in self.room_by_id:
            self.logging.warning("L WARNING! (create_room) Room with room_id: %s have been already created! "
                                 "Skip. new-room_model: %s old-room: %s", room_id, room_model, self.room_by_id[room_id])
            return None

        # Create
        room_class = self.house_config.room_class
        room = room_class(self.house_config, room_model)
        room.on_game_state_changed = self.house.try_save_house_state_on_change

        # Add
        room.lobby = self
        self.room_by_id[room_id] = room
        self.room_list.append(room)

        # Sort
        # (Maybe sort by min_stake and room_name?)
        self.room_list.sort(key=lambda room_item: "{0:>3}".format(room_item.room_id))
        # -self.room_list.sort(key=lambda room:
        #     int(room.room_id) if str(room.room_id).isdigit() else room.room_id)

        return room

    def _create_room_model(self, room_info_or_model):
        if isinstance(room_info_or_model, RoomModel):
            return room_info_or_model

        room_info = room_info_or_model
        # room_id
        room_id = (room_info["room_id"] if "room_id" in room_info else room_info[0]) or 0
        while str(room_id) in self.room_by_id:
            if not isinstance(room_id, int):
                room_id = 0
            room_id += 1
        if "room_id" in room_info:
            room_info["room_id"] = str(room_id)
        else:
            room_info[0] = str(room_id)

        # Create
        room_model = RoomModel.create_model(room_info)
        return room_model

    def _dispose_room(self, player, room_id):
        room_id = str(room_id)
        if not room_id or room_id not in self.room_by_id:
            self.logging.warning("L WARNING! (dispose_room) Wrong room_id: %s room_by_id: %s", room_id, self.room_by_id)
            return False

        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        """:type : Room"""
        if not room:
            self.logging.warning("L WARNING! (dispose_room) There is no room instance with "
                                 "room_id: %s room: %s room_by_id: %s", room_id, room, self.room_by_id)
            return False

        owner_user_id = room.room_model.owner_user_id
        if not owner_user_id or owner_user_id != player.user_id:
            self.logging.warning("L WARNING! (dispose_room) User should be the room owner to be able to delete the room"
                                 " room_id: %s room-owner: %s player-user_id: %s", room_id,
                                 owner_user_id, player.user_id)
            return False

        # Dispose
        room.dispose()
        return True

    def remove_room(self, room):
        if room and room in self.room_list:
            # Remove
            del self.room_by_id[room.room_id]
            self.room_list.remove(room)
            room.lobby = None

    # Commands for protocol
    # (Create/Remove rooms)

    # todo create_private_room-> create_room command (and edit and delete too)
    def create_room(self, player, room_info):
        """
        :param player:
        :param room_info: 0th (room_id) should be None to set room_id automatically
        :return:
        """

        room = self._create_room(room_info, owner_player=player)
        if room:
            self.get_room_info(player, room.room_id)
        else:
            self.logging.error("L WARNING! (create_room) Failed to create the room with "
                               "room_info: %s for player: %s", room_info, player)
            self.get_room_info(player, None)

    def edit_room(self, player, room_info):
        room_id = str(room_info[0])
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        # todo extract all owner checks to method
        owner_user_id = room.room_model.owner_user_id if room else None
        if room and owner_user_id and owner_user_id == player.user_id:
            # todo try apply_changes() if possible (or set is_change_on_command=True inside the room (or game)
            #  for each instance when game is on and applying impossible and set to False between games (??-))
            room.room_model.import_data(room_info)
            room.check_and_apply_changes()
            # # (Theoretically, it's possible to )
            # if player.room != room:
            #     self.get_room_info(player, room_id)
            # (Response is needed as acknowledgement)
            self.get_room_info(player, room_id)
        else:
            if not room:
                self.logging.warning("L WARNING! (edit_room) There is no room with "
                                     "room_id: %s from room_info: %s player: %s", room_id, room_info, player)
            else:
                self.logging.warning("L WARNING! (edit_room) Specified user is not room's owner! "
                                     "room_id: %s from room_info: %s player: %s", room_id, room_info, player)
            self.get_room_info(player, None)

    def delete_room(self, player, room_id):
        if self._dispose_room(player, room_id):
            self.get_room_list(player)
        else:
            self.logging.warning("L WARNING! (delete_room) Cannot remove the room with "
                                 "room_id: %s player: %s", room_id, player)

    # (Use rooms)

    def get_room_by_id(self, room_id):
        room_id = str(room_id)
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        if not room:
            self.logging.warning("L WARNING! There is no room with room_id: %s", room_id)
        return room

    def get_room_list(self, player):
        player.protocol.rooms_list(self.rooms_export_public_data(player))

    def find_free_room(self, player, find_and_join=FindAndJoin.JOIN_ROOM, game_id=-1,
                       game_variation=None, game_type=-1, room_type=-1, max_stake=0):
        """
        :param player
        :param find_and_join see FindAndJoin (0-just find, 1-find and join a room, 2-find and join a game)
        :param game_id
        :param game_type
        :param game_variation
        :param room_type
        :param max_stake
        """

        free_room = None
        empty_room = None
        # Find
        for room in self.room_list:
            room_model = room.room_model
            # Check matching room_code (game_id, game_type, room_type)
            if (game_id >= 0 and game_id != room_model.game_id) or \
                    (game_variation is not None and game_variation != room_model.game_variation) or \
                    (game_type >= 0 and game_type != room_model.game_type) or \
                    (room_type >= 0 and room_type != room_model.room_type):
                # self.logging.debug("temp (find_free_room) iterated room: %s doesn't fit the "
                # "game_id, game_type, room_type: %s %s %s", room, game_id, game_type, room_type)
                continue
            if room_model.max_stake != max_stake > 0:
                continue

            if max_stake < 0:
                # todo choose room considering player's money and room's stakes
                pass

            # Check not full and not empty room
            if room.has_free_seat_to_play and not room.is_empty_room:
                free_room = room
                break
            # Save first empty_room for the last case
            if not empty_room and room.is_empty_room and \
                    (room_model.min_buy_in <= 0 or player.money_amount >= room_model.min_buy_in):
                empty_room = room

        # ?Find room not considering max_stake
        # if not free_room and max_stake > 0:
        #     self.find_free_room(player, find_and_join, game_id, game_type, room_type)
        #     return

        # If there is no free seat in nonempty rooms (rooms with players) use empty room
        if not free_room:
            free_room = empty_room

        self.logging.debug("temp (find_free_room) free_room: %s for player: %s", free_room, player)
        # Join
        if free_room:
            if find_and_join == FindAndJoin.JUST_FIND:
                self.get_game_info(player, free_room.room_id, True)
            elif find_and_join == FindAndJoin.JOIN_ROOM:
                self.join_the_room(player, free_room.room_id)
            elif find_and_join == FindAndJoin.JOIN_GAME:
                self.join_the_game(player, free_room.room_id, money_in_play=free_room.room_model.max_buy_in)
        else:
            self.logging.warning("L WARNING! (find_free_room) Cannot find any free_room: %s player: %s",
                                 free_room, player)
            # TODO create new temp room (?) (or choose not free room (-)) or go to another server (+)
            self.get_game_info(player, -1)

        # (Return for subclasses)
        return free_room

    def get_room_info(self, player, room_id):
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        # todo add player_info_list (visitors+players) on house_config.is_room_visitors_displayed
        # ?room_info(None)
        if room and room.room_model.is_private and room.room_model.owner_user_id != player.user_id:
            room = None

        player.protocol.room_info(room.room_model.export_public_data() if room else None)

    def get_game_info(self, player, room_id, is_get_room_content=False):
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        if room and (not room.room_model.is_private or
                     room.room_model.owner_user_id == player.user_id or
                     room == player.room):
            room.get_game_info(player, is_get_room_content)
        else:
            player.protocol.game_info(None, None)

    def get_player_info_in_game(self, asking_player, room_id, place_index):
        """get_player_info() by room_id"""
        room = self.room_by_id[room_id] if room_id in self.room_by_id else None
        if not room:
            self.logging.warning("L WARNING! (get_player_info_in_game) There is no room with room_id: %s", room_id)
            return
        if not room.game:
            # If play not created hence there are no players in it
            asking_player.protocol.player_info(place_index, None)
        else:
            room.game.get_player_info(asking_player, place_index)

    def join_the_room(self, player, room_id=None, password=None):
        """Only as visitor"""
        room = self.get_room_by_id(room_id or player.room_id)
        if not room:
            return None

        # self.logging.debug("L temp (join_the_room) %s %s %s"
        # "player: %s player.room: %s", room, room_id, self.room_by_id, player, player.room)
        # todo check unittests (removed can_be_added_as_player calling)
        if not room.can_be_added_as_visitor(player):
            self.logging.warning("L WARNING! (join_the_game) Cannot join the room! "
                                 "No more free space for visitors.. "
                                 "room_id: %s player: %s max_visitors: %s cur_visitors: %s", room_id, player,
                                 room.room_model.max_visitor_count, room.room_model.visitor_count)
            return None
        return self._do_join_the_room(player, room_id, password)

    # todo add to unittests the case where we try to join full game and thou have been rejected
    # without joining the room
    def join_the_game(self, player, room_id=None, password=None, place_index=-1, money_in_play=0):
        """Only as player"""
        room = self.get_room_by_id(room_id or player.room_id)
        if not room:
            return None

        if not room.can_be_added_as_player(player, place_index, money_in_play):
            self.logging.warning("L WARNING! (join_the_game) Cannot join the game! "
                                 "Maybe no free seats or game is already started. "
                                 "room_id: %s player: %s", room_id, player)
            return None

        room = self._do_join_the_room(player, room_id or player.room_id, password)
        if room and room.join_the_game(player, place_index, money_in_play):
            # if player in self.present_player_set:
            #     self.present_player_set.remove(player)
            if player.is_connected:
                self.logging.debug("L (join_the_game) [try_save] player: %s", player)
                self.house.try_save_house_state_on_change()
        else:
            self.logging.warning("L WARNING! (join_the_game) Cannot join! Player didn't joined the "
                                 "room: %s for player: %s", room, player)

    def _do_join_the_room(self, player, room_id=None, password=None):
        room = self.get_room_by_id(room_id or player.room_id)
        if not room:
            return None

        # Check player is already in some another room
        if room == player.room:
            return room
        if player.room:  # and player.room != room:  # and not self.house_model.is_allow_multisession_in_the_room:
            self.leave_the_room(player)

        # Enter the room
        if room.add_player(player, password) and player in self.present_player_set:
            self.present_player_set.remove(player)

        if player.is_connected:
            self.logging.debug("L (join_the_room) [try_save] player: %s", player)
            self.house.try_save_house_state_on_change()
        return room

    def leave_the_game(self, player):
        room = player.room if player else None
        if room and room.leave_the_game(player):
            if player.is_connected:
                self.logging.debug("L (leave_the_game) [try_save] player: %s", player)
                self.house.try_save_house_state_on_change()
        else:
            self.logging.warning("L WARNING! (leave_the_game) Cannot leave! Player not in the "
                                 "room: %s for player: %s", room, player)

    def leave_the_room(self, player):
        room = player.room if player else None
        if room:
            if room.remove_player(player):
                self.present_player_set.add(player)

            if player.is_connected:
                self.logging.debug("L (leave_the_room) [try_save] player: %s", player)
                self.house.try_save_house_state_on_change()
        else:
            self.logging.warning("L WARNING! (leave_the_room) Cannot leave! Player not in the "
                                 "room: %s for player: %s", room, player)


class Lobby(RoomManager, ExportableMixIn):
    """
    Tournaments further implementation notes.
    (For classical tournaments we may create Tournament and TournamentModel classes
    to be managed by Lobby and used by Room. Tournament data would be defined in tournament.json.
    Each room data would have tournament_id, and lobby for room_info_list request would return
    only one room of the same tournament_id.)
    """

    logging = None

    @property
    def lobby_id(self):
        return self.lobby_model.lobby_id if self.lobby_model else None

    # _is_paused = False
    #
    # @property
    # def is_paused(self):
    #     """Used in protocol - don't process any command if paused"""
    #     return self._is_paused

    # Save/Restore

    @property
    def _property_names(self):
        return ["model_data", "rooms_data"]

    @property
    def model_data(self):
        return self.lobby_model.export_data()

    @model_data.setter
    def model_data(self, value):
        if value is None:
            return
        self.lobby_model.import_data(value)
        # (For restoring)
        self.lobby_model.apply_changes()

    def __init__(self, house, lobby_model):
        # Model
        self.house_config = house.house_config if house else None
        self.house_model = self.house_config.house_model if self.house_config else None
        self.lobby_model = lobby_model
        """:type: HouseConfig"""

        self.logging = logging.getLogger("LOBBY")
        self.logging.debug("L Create Lobby %s", self.house_config.house_id)  # , self.house_config.room_info_list)
        # UserManager.__init__(self, house_config)
        RoomManager.__init__(self, house, lobby_model)
        ExportableMixIn.__init__(self)

        # self.entered_player_set = set()
        # All players entered the lobby, staying there or joined the rooms
        self.player_set = set()
        # Set of players currently present in the lobby
        self.present_player_set = set()

    def dispose(self):
        # UserManager.dispose(self)
        RoomManager.dispose(self)

        self.house_config = None
        self.house_model = None
        # self.logging = None

        self.player_set.clear()
        self.present_player_set.clear()

    def __repr__(self):
        return "<{0} id:{1} name:{2} room_count:{3} player_count:{4}>".format(
            self.__class__.__name__, self.house_config.house_id, self.house_config.house_name,
            len(self.room_by_id), len(self.player_set))

    def pause(self):
        # self._is_paused = True
        for room in self.room_list:
            if room.game:
                room.game.pause_game()

    def resume(self):
        # self._is_paused = False
        for room in self.room_list:
            if room.game:
                room.game.resume_game()

    # Players

    def add_player(self, player):
        # if self.is_paused:
        #     return

        if player.lobby and player.lobby != self:
            # Remove from previous
            player.lobby.remove_player(player)

        player.lobby = self
        self.player_set.add(player)
        self.present_player_set.add(player)

        # (On restore player is not connected, so it won't be a problem to send goto_lobby while in game)
        player.protocol.goto_lobby(self.lobby_model.export_public_data())

        # Restore in room and game (if player is restoring: after reconnect or server recovered)
        if player.room_id:
            if player.place_index >= 0:
                self.join_the_game(player, place_index=player.place_index)
            else:
                self.join_the_room(player)

    def remove_player(self, player):
        if player not in self.player_set:
            return

        self.leave_the_room(player)

        if player in self.present_player_set:
            self.present_player_set.remove(player)
        self.player_set.remove(player)
        player.lobby = None

    def send_message(self, message_type, text, sender_player, receiver_id=-1):
        is_message_private = MessageType.is_message_private(message_type)
        for player in self.present_player_set:
            # if not is_message_private or receiver_id < 0 or player.user_id == receiver_id:
            if not is_message_private or player.user_id == receiver_id:
                player.protocol.send_message(message_type, text, sender_player, receiver_id)
