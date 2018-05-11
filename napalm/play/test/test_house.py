import json
import os
from unittest import TestCase
from unittest.mock import Mock, MagicMock

from napalm.core import ExportableMixIn
from napalm.play.core import HouseConfig
from napalm.play.game import GameConfigModel
from napalm.play.house import Player, User, House, HouseModel
from napalm.play.lobby import Lobby, LobbyModel, RoomModel
from napalm.play.poker.game import PokerGameConfigModel
from napalm.play.poker.lobby import PokerRoomModel, PokerRoom
from napalm.play.protocol import MessageType
from napalm.play.service import GameService
from napalm.play.test.test_core import MyLobbyModel, MyHouseModel
from napalm.socket.protocol import Protocol


# Utility
def assert_properties(self, object, names, values, check_not_empty=True):
    for name, value in zip(names, values):
        if check_not_empty:
            self.assertIsNotNone(value)
            self.assertNotEqual(value, "")

        self.assertEqual(getattr(object, name), value)


class TestPlayer(TestCase):
    player = None

    def setUp(self):
        super().setUp()

        self.player = Player()

        self.player.user = User()
        self.player.user.import_data(["1234", "76543", "Sidor", "Kovpak",
                                      "avatar.url", "avatar.url.small", "avatar.url.normal",
                                      15, 120000, 1,
                                      "2017-01-01", 5])

    def test_super(self):
        self.assertIsInstance(self.player, ExportableMixIn)

    def test_dispose(self):
        self.player.house = house = MagicMock()
        self.player.lobby = lobby = MagicMock()
        self.player.room = room = MagicMock()
        self.player.user = user = MagicMock()
        self.player.house_config = Mock()
        self.player.protocol = Mock()
        self.player.lobby_id = "some"
        self.player.room_id = "some"
        self.player.place_index = 4
        self.player.is_playing = True
        self.player.logging = Mock()

        self.player.dispose()

        house.remove_player.assert_called_once_with(self.player)
        lobby.remove_player.assert_called_once_with(self.player)
        room.remove_player.assert_called_once_with(self.player)
        user.remove_player.assert_called_once_with(self.player)
        self.assertIsNone(self.player.house)
        self.assertIsNone(self.player.lobby)
        self.assertIsNone(self.player.room)
        self.assertIsNone(self.player.user)
        self.assertIsNone(self.player.house_config)
        self.assertIsNone(self.player.protocol)
        self.assertIsNone(self.player.lobby_id)
        self.assertIsNone(self.player.room_id)
        self.assertEqual(self.player.place_index, -1)
        self.assertEqual(self.player.is_playing, False)
        self.assertIsNone(self.player.logging)

    def test_properties(self):
        # Mainly used for import

        property_names = ["user_id", "session_id", "lobby_id", "room_id", "place_index", "is_playing",
                          "money_in_play", "gift_image_url"]
        initial_values = ["", -1, None, None, -1, False,
                          0, ""]
        assert_properties(self, self.player, property_names, initial_values, False)

        new_values = ["1234", 2, 1, 11, 4, True, 1000, "some.gift.url"]
        self.player.import_data(new_values)
        exported_values = self.player.export_data()

        assert_properties(self, self.player, property_names, new_values)
        self.assertEqual(exported_values, new_values)

        # Assert lobby_id and room_id updated from lobby and room when exporting
        new_values[2] = "1144"
        new_values[3] = "5577"
        self.player.lobby = Mock(lobby_id="1144")
        self.player.room = Mock(room_id="5577")

        exported_values = self.player.export_data()

        self.assertEqual(exported_values, new_values)

    def test_public_properties(self):
        # Mainly used for export (for client)

        new_values = ["000", 2, 1, 11, 4, True, 1000, "some.url"]
        self.player.import_data(new_values)
        property_names = ["user_id", "social_id", "first_name", "last_name",
                          "image_url", "image_url_small", "image_url_normal",
                          "level", "money_amount", "money_in_play", "is_in_game",
                          "join_date", "gift_image_url", "vip_days_available",
                          "is_playing"]

        exported_values = self.player.export_public_data()

        # (Assert property names ain't changed)
        assert_properties(self, self.player, property_names, exported_values)
        self.assertEqual(exported_values, ["1234", "76543", "Sidor", "Kovpak",
                                           "avatar.url", "avatar.url.small", "avatar.url.normal",
                                           15, 1000, 120000, 1,
                                           "2017-01-01", "some.gift.url", 5,
                                           True])

    def test_connected(self):
        self.assertFalse(self.player.is_connected)

        self.player.protocol = Protocol()

        self.assertFalse(self.player.is_connected)

        # (Make is_ready return True)
        self.player.protocol.send_bytes_method = "some"

        self.assertTrue(self.player.is_connected)

    def test_update_self_user_info(self):
        self.player.user = Mock(update_self_user_info=lambda: ["a", "b", "c"])
        self.player.protocol = MagicMock()

        self.player.update_self_user_info()

        self.player.protocol.update_self_user_info.assert_called_with(["a", "b", "c"])

    # Money

    def test_add_money_in_play(self):
        min_buy_in = 1000
        max_buy_in = 2000
        self.player.user.money_amount = 5000

        self.player.user._service = Mock(decrease=lambda money: {"money": money})
        self.player.update_self_user_info = Mock()
        self.assertEqual(self.player.money_in_play, 0)

        # Not in a room and game
        self.player.add_money_in_play(1000)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 5000)

        # Not in a game
        self.player.room = Mock(room_model=Mock(min_buy_in=min_buy_in, max_buy_in=max_buy_in))
        self.player.add_money_in_play(1000)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 5000)

        # Empty amount
        self.player.game = Mock()
        self.player.add_money_in_play(0)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 5000)
        # (Reset mock)
        self.player.user._service.decrease.reset_mock()

        # Below min_buy_in
        self.player.add_money_in_play(500)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 5000)

        # Between min_buy_in and max_buy_in
        self.player.add_money_in_play(1500)

        self.player.user._service.decrease.assert_called_with(1500)
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 1500)
        self.assertEqual(self.player.user.money_amount, 3500)
        # (Reset mock)
        self.player.user._service.decrease.reset_mock()
        self.player.update_self_user_info.reset_mock()

        # Above max_buy_in
        self.player.add_money_in_play(3000)

        self.player.user._service.decrease.assert_called_with(500)
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 2000)
        self.assertEqual(self.player.user.money_amount, 3000)
        # (Reset mock)
        self.player.user._service.decrease.reset_mock()
        self.player.update_self_user_info.reset_mock()

        # Above max_buy_in again
        self.player.add_money_in_play(3000)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 2000)
        self.assertEqual(self.player.user.money_amount, 3000)

    def test_add_money_in_play_with_low_user_money(self):
        min_buy_in = 1000
        max_buy_in = 2000
        # User money below max_buy_in
        self.player.user.money_amount = 1500

        self.player.room = Mock(room_model=Mock(min_buy_in=min_buy_in, max_buy_in=max_buy_in))
        self.player.game = Mock()

        self.player.user._service = Mock(decrease=lambda money: {"money": money})
        self.player.update_self_user_info = Mock()
        self.assertEqual(self.player.money_in_play, 0)

        # Between min_buy_in and max_buy_in
        self.player.add_money_in_play(1000)

        self.player.user._service.decrease.assert_called_with(1000)
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 1000)
        self.assertEqual(self.player.user.money_amount, 500)

        # Above max_buy_in
        self.player.add_money_in_play(3000)

        self.player.user._service.decrease.assert_called_with(500)
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 1500)
        self.assertEqual(self.player.user.money_amount, 0)
        # (Reset mock)
        self.player.user._service.decrease.reset_mock()
        self.player.update_self_user_info.reset_mock()

        # Above max_buy_in again
        self.player.add_money_in_play(3000)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 1500)
        self.assertEqual(self.player.user.money_amount, 0)

    def test_add_money_in_play_with_very_low_user_money(self):
        min_buy_in = 1000
        max_buy_in = 2000
        # User money below min_buy_in
        self.player.user.money_amount = 500

        self.player.room = Mock(room_model=Mock(min_buy_in=min_buy_in, max_buy_in=max_buy_in))
        self.player.game = Mock()

        self.player.user._service = Mock(decrease=lambda money: {"money": money})
        self.player.update_self_user_info = Mock()
        self.assertEqual(self.player.money_in_play, 0)

        # Between min_buy_in and max_buy_in
        self.player.add_money_in_play(1000)

        self.player.user._service.decrease.assert_not_called()
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 500)

    def test_remove_money_in_play(self):
        self.player.money_in_play = 1500
        self.player.user.money_amount = 500

        self.player.user._service = Mock(increase=lambda money: {"money": money})
        self.player.update_self_user_info = Mock()
        self.assertEqual(self.player.money_in_play, 0)

        # Call
        self.player.remove_money_in_play()

        self.player.user._service.increase.assert_called_with(1500)
        self.player.update_self_user_info.assert_called_once()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 1500)
        # (Reset mock)
        self.player.user._service.increase.reset_mock()
        self.player.update_self_user_info.reset_mock()

        # Call again
        self.player.remove_money_in_play()

        self.player.user._service.increase.assert_not_called()
        self.player.update_self_user_info.assert_not_called()
        self.assertEqual(self.player.money_in_play, 0)
        self.assertEqual(self.player.user.money_amount, 1500)


class TestPlayerManager:
    user = None

    def test_players_data(self):
        self.user.player_set.clear()
        self.user.player_by_session_id.clear()

        property_names = ["session_id", "lobby_id", "room_id", "place_index",
                          "is_playing", "money_in_play", "gift_image_url"]
        players_data = [[3, "1", None, -1, False, 0, "some.gift.url"],
                        [5, "1", "3", 3, False, 1000, None]]

        self.user.players_data = players_data

        self.assertEqual(len(self.user.players_set), 2)
        assert_properties(self, self.user.player_by_session_id[3], property_names, players_data[0])
        assert_properties(self, self.user.player_by_session_id[5], property_names, players_data[1])
        self.assertTrue(players_data[0] in self.user.players_data)
        self.assertTrue(players_data[1] in self.user.players_data)

        self.assertEqual(self.user.players_data, players_data)

        # Adds new players - Not intended to be called more than once (only on restore)
        self.user.players_data = players_data

        self.assertEqual(len(self.user.players_set), 4)

    def test_player_manager_constructor(self):
        user = User()

        self.assertEqual(user.player_set, set())
        self.assertEqual(user.player_by_session_id, {})
        self.assertEqual(user.disconnected_player_by_session_id, {})
        self.assertEqual(user.max_session_id, None)

    def test_player_manager_dispose(self):
        players = [MagicMock(), MagicMock()]
        for player in players:
            self.user.add_player(player)
        self.user.on_disconnect(players[0])

        self.assertNotEqual(self.user.player_set, set())
        self.assertNotEqual(self.user.player_by_session_id, {})
        self.assertNotEqual(self.user.disconnected_player_by_session_id, {})

        self.user.dispose()

        for player in players:
            player.dispose.assert_called_once()
            self.assertIsNone(player.user)
        self.assertEqual(self.user.player_set, set())
        self.assertEqual(self.user.player_by_session_id, {})
        self.assertEqual(self.user.disconnected_player_by_session_id, {})
        self.assertIsNone(self.user.house_config)
        self.assertIsNone(self.user.house_model)

    def test_on_connect_and_disconnect(self):
        # 2 players were already added
        self.assertEqual(len(self.user.player_set), 2)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

        # Create new player
        player = self.user.on_connect(protocol=Mock())

        self.assertEqual(player.session_id, 2)
        self.assertEqual(len(self.user.player_set), 3)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

        # Disconnect
        self.user.on_disconnect(player)

        self.assertEqual(len(self.user.player_set), 3)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player})

        # Create new disconnected player
        player2 = self.user.on_connect(session_id=5)

        self.assertEqual(player2.session_id, 5)
        self.assertEqual(len(self.user.player_set), 4)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 5])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player, 5: player2})

        # Connect disconnected player
        player3 = self.user.on_connect(Mock(), 5)

        self.assertEqual(player3, player2)
        self.assertEqual(len(self.user.player_set), 4)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 5])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player})

        # Try to connect by same session_id
        player4 = self.user.on_connect(Mock(), 5)

        self.assertNotEqual(player4, player3)
        self.assertEqual(player4.session_id, 6)
        self.assertEqual(len(self.user.player_set), 5)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 5, 6])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player})

        # Connect to some disconnected player with no session_id specified
        player5 = self.user.on_connect(protocol=Mock())

        self.assertEqual(player5, player)
        self.assertEqual(player5.session_id, 2)
        self.assertEqual(len(self.user.player_set), 5)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 5, 6])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

        # Connecting again will create new player as there are no more disconnected players
        player6 = self.user.on_connect(protocol=Mock())

        self.assertEqual(player6.session_id, 3)
        self.assertEqual(len(self.user.player_set), 6)
        self.assertEqual(set(self.user.player_by_session_id.keys()), set([0, 1, 2, 5, 6, 3]))
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 5, 6, 3])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

    def test_add_player(self):
        # 2 players were already added
        self.assertEqual(len(self.user.player_set), 2)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

        # Add connected player with defined session_id
        player2 = Player(Mock(), 4, Mock())
        self.user.add_player(player2)

        self.assertEqual(len(self.user.player_set), 3)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 4])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})

        # Add disconnected player with undefined session_id
        player = Player(Mock())
        self.user.add_player(player)

        self.assertEqual(len(self.user.player_set), 4)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2, 4])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player})

    def test_remove_player(self):
        self.user.dispose = Mock()
        # Add disconnected player with undefined session_id
        player = Player(Mock())
        self.user.add_player(player)
        # 2 players were already added + 1 new
        self.assertEqual(len(self.user.player_set), 3)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1, 2])
        self.assertEqual(self.user.disconnected_player_by_session_id, {2: player})
        self.user.dispose.assert_not_called()

        # Remove disconnected player
        self.assertEqual(player.user, self.user)

        self.user.remove_player(player)

        self.assertIsNone(player.user)
        self.assertEqual(len(self.user.player_set), 2)
        self.assertEqual(self.user.player_by_session_id.keys(), [0, 1])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})
        self.user.dispose.assert_not_called()

        # Remove connected player
        player = self.user.player_by_session_id[0]
        self.assertEqual(player.user, self.user)

        self.user.remove_player(player)

        self.assertIsNone(player.user)
        self.assertEqual(len(self.user.player_set), 1)
        self.assertEqual(self.user.player_by_session_id.keys(), [1])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})
        self.user.dispose.assert_not_called()

        # Remove the last player
        player = self.user.player_by_session_id[1]
        self.assertEqual(player.user, self.user)

        self.user.remove_player(player)

        self.assertIsNone(player.user)
        self.assertEqual(len(self.user.player_set), 0)
        self.assertEqual(self.user.player_by_session_id.keys(), [])
        self.assertEqual(self.user.disconnected_player_by_session_id, {})
        self.user.dispose.assert_called_once()


class TestUser(TestCase, TestPlayerManager):
    user = None
    players = None
    values = None

    def setUp(self):
        # TestPlayerManager.setUp(self)

        self.values = ["1234", "76543", "Sidor", "Kovpak",
                       "avatar.url", "avatar.url.small", "avatar.url.normal",
                       15, 120000, 1,
                       "2017-01-01", 5]

        # (Make house_config.service_class(...).check_auth_sig() -> True)
        # house_config = Mock(service_class=lambda *args: MagicMock(check_auth_sig=True))
        house_config = HouseConfig(house_id=1, data_dir_path="initial_configs")
        house_config.service_class=lambda *args: MagicMock(check_auth_sig=True)
        self.user = User(house_config)

        self.user.import_data(self.values)

        # Add players
        self.players = [MagicMock(spec=Player), MagicMock(spec=Player)]
        self.players[0].money_in_play = 1100
        self.players[0].protocol = Mock()
        self.players[1].money_in_play = 5550
        self.players[1].protocol = Mock()
        for player in self.players:
            self.user.add_player(player)

    def test_properties(self):
        exported_values = self.user.export_data()
        exported_public_values = self.user.export_public_data()

        self.assertEqual(self.user.total_money_amount, 126650)
        self.assertEqual(exported_values[:len(self.values)], self.values)
        self.assertEqual(exported_public_values, self.values)
        self.assertEqual(len(self.user.players_data), 2)

    def test_super(self):
        self.assertIsInstance(self.user, ExportableMixIn)

    def test_constructor(self):
        self.assertIsNotNone(self.user.house_config)
        self.assertEqual(self.user.house_model, self.user.house_config.house_model)
        self.assertIsNotNone(self.user._service)
        self.assertIsInstance(self.user._service, self.user.house_config.service_class)

        self.assertEqual(self.user.user_id, "1234")
        self.assertEqual(self.user.social_id, "76543")

    def test_dispose(self):
        self.user.house = house = MagicMock()
        service = self.user._service

        self.user.dispose()

        house.remove_user.assert_called_once_with(self.user)
        service.dispose.assert_called_once()

        self.assertIsNone(self.user.house)
        self.assertIsNone(self.user._service)
        self.assertIsNone(self.user.house_config)
        self.assertIsNone(self.user.logging)
        self.assertIsNone(self.user.user_id)
        self.assertIsNone(self.user.social_id)

    # Protocol

    # def test_send_message(self):
    #     sender = Mock(user_id="798")
    #
    #     # Send message to all self.user's players
    #     self.user.send_message(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text", sender)
    #
    #     for player in self.user.player_set:
    #         player.protocol.send_message.assert_called_once_with(
    #             MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text", "789", self.user.user_id)

    # Service

    def test_check_credentials(self):
        self.user._service.check_auth_sig = Mock(return_value=True)
        self.assertEqual(self.user.social_id, "1234")

        # With one param empty
        result = self.user.check_credentials("1234", "dddddd", "")

        self.assertFalse(result)
        self.user._service.check_auth_sig.assert_not_called()

        # With one param empty
        result = self.user.check_credentials("", "dddddd", "asdf")

        self.assertFalse(result)
        self.user._service.check_auth_sig.assert_not_called()

        # With one param empty
        result = self.user.check_credentials("1234", "", "asdf")

        self.assertFalse(result)
        self.user._service.check_auth_sig.assert_not_called()

        # Wrong social_id
        result = self.user.check_credentials("001234", "dddddd", "asdf")

        self.assertFalse(result)
        # (social_id is already set before)
        self.assertEqual(self.user.social_id, "1234")
        self.user._service.check_auth_sig.assert_not_called()

        # Check OK
        result = self.user.check_credentials("1234", "dddddd", "asdf")

        self.assertTrue(result)
        self.assertEqual(self.user.social_id, "1234")
        self.user._service.check_auth_sig.assert_called_once_with("1234", "dddddd", "asdf")

        # Check OK setting social_id
        self.user.social_id = ""
        result = self.user.check_credentials("001234", "dddddd", "asdf")

        # (social_id set)
        self.assertTrue(result)
        self.assertEqual(self.user.social_id, "001234", "temp")
        self.user._service.check_auth_sig.assert_called_with("001234", "dddddd", "asdf", {"some": "for_test_value"})

    def test_remove_all_money_in_play(self):
        self.user._service.increase = Mock(side_effect=lambda money: {"money": money})

        result = self.user.remove_all_money_in_play()

        self.assertEqual(result, 6650)
        for player in self.user.player_by_session_id.values():
            self.assertEqual(player.money_in_play, 0)
        self.user._service.increase.assert_called_once_with(6650)
        self.assertEqual(self.user.money_amount, 126650)

    def test_take_money(self):
        self.user._service.decrease = Mock(side_effect=lambda money: {"money": money})

        # < 0
        result = self.user.take_money(-1, -10)

        self.assertEqual(result, 0)
        self.user._service.decrease.assert_not_called()

        # 0
        result = self.user.take_money(0, 0)

        self.assertEqual(result, 0)
        self.user._service.decrease.assert_not_called()

        # Under min_amount
        result = self.user.take_money(1100, 1200)

        self.assertEqual(result, 0)
        self.user._service.decrease.assert_not_called()

        # OK
        result = self.user.take_money(1100, 100)

        self.assertEqual(result, 1100)
        self.user._service.decrease.assert_called_once_with(1100)
        self.assertEqual(self.user.money_amount, 118900)

        # OK - more than user has
        result = self.user.take_money(110000000, 100)

        self.assertEqual(result, 118900)
        self.user._service.decrease.assert_called_once_with(118900)
        self.assertEqual(self.user.money_amount, 0)

    def test_put_money_back(self):
        self.user._service.increase = Mock(side_effect=lambda money: {"money": money})

        # < 0
        result = self.user.put_money_back(-1)

        self.assertEqual(result, 0)
        self.user._service.increase.assert_not_called()

        # 0
        result = self.user.put_money_back(0)

        self.assertEqual(result, 0)
        self.user._service.increase.assert_not_called()

        # OK
        result = self.user.put_money_back(1100)

        self.assertEqual(result, 1100)
        self.user._service.increase.assert_called_once_with(1100)
        self.assertEqual(self.user.money_amount, 121100)

    def test_update_self_user_info(self):
        user_info = ["1234", "76543", "Sidor", "Kovpak", "url1", "url2", "url3",
                     15, 120000, 1, "2017-01-01", 5]
        self.assertEqual(self.user.export_data(), user_info)

        user_info2 = ["1234", "76543", "Sidor", "Kovpak", "url1#", "url2#", "url3#",
                      16, 125500, 2, "2017-01-01", 6]
        self.user._service.getCurrentUserFullInfo = Mock(side_effect=lambda money: user_info2)

        self.user.update_self_user_info()

        self.assertNotEqual(self.user.export_data(), user_info)
        self.assertEqual(self.user.export_data(), user_info2)
        for player in self.user.player_by_session_id.values():
            player.update_self_user_info.assert_called_once()

    def test_gameEnd(self):
        self.user._service.gameEnd = Mock()

        # OK (With defaults)
        self.user.gameEnd({"a": 1}, [1, 2, 3])

        self.user._service.gameEnd.assert_called_with({"a": 1}, [1, 2, 3], False, False)

        # OK
        self.user.gameEnd({"a": 1}, [1, 2, 3], True, True)

        self.user._service.gameEnd.assert_called_with({"a": 1}, [1, 2, 3], True, True)


class TestUserManager:

    house = None

    def test_users_and_players_count(self):
        self.assertEqual(self.house.users_online, 0)
        self.assertEqual(self.house.players_online, 0)
        self.assertEqual(self.house.players_connected, 0)

        auth_sig = GameService.make_auth_sig("123", "token1", "my_secret")
        self.house.on_player_connected(Mock(), "123", "token1", auth_sig, "test")
        auth_sig = GameService.make_auth_sig("123", "token2", "my_secret")
        self.house.on_player_connected(Mock(), "123", "token2", auth_sig, "test")
        auth_sig = GameService.make_auth_sig("456", "token3", "my_secret")
        self.house.on_player_connected(None, "456", "token3", auth_sig, "test")

        self.assertEqual(self.house.users_online, 2)
        self.assertEqual(self.house.players_online, 3)
        self.assertEqual(self.house.players_connected, 2)

    def test_users_data(self):
        self.assertEqual(self.house.users_online, 0)

        # Setter
        users_data = {"123": ["123", "76543", "", "", "", "", "", "", "", "", "", "",
                              # player_info: "session_id", "lobby_id", "room_id", "place_index"
                              [[0, "1", "2", 2], [0, "1", "3", -1]]],
                      "456": ["456", "54243", "", "", "", "", "", "", "", "", "", "",
                              [[0, "1", "2", 3]]]}
        self.house.users_data = users_data

        self.assertEqual(self.house.users_online, 2)
        self.assertEqual(self.house.players_online, 2)
        self.assertEqual(self.house.players_connected, 0)
        self.assertEqual(self.house.house_model.players_online, self.house.players_online)
        self.assertEqual(self.house._retrieve_user("123").social_id, "76543")
        self.assertEqual(self.house._retrieve_user("456").social_id, "54243")
        # Assert user_data -> add_user -> goto_lobby
        player1_1 = self.house._retrieve_user("123").player_by_session_id[0]
        player1_2 = self.house._retrieve_user("123").player_by_session_id[1]
        player2_1 = self.house._retrieve_user("456").player_by_session_id[0]
        self.assertIsNotNone(player1_1.game)
        self.assertIsNone(player1_2.game)
        self.assertEqual(player1_1.game, player2_1.game)
        self.assertEqual(player1_1.game.room_id, "2")
        self.assertEqual(player1_1.room.room_id, "2")
        self.assertEqual(player1_1.lobby.lobby_id, "1")
        self.assertEqual(player1_1.place_index, 2)
        self.assertEqual(player2_1.place_index, 3)

        # Getter
        self.assertEqual(self.house.users_data, users_data)

        # Add user
        self.house.on_player_connected(Mock(), "678")

        self.assertEqual(self.house.users_data["678"][0], "678")

    def test_constructor(self):
        self.assertIsNotNone(self.house.house_config)
        self.assertEqual(self.house._user_by_id, {})
        self.assertEqual(self.house._is_restoring_now, False)
        self.assertIsInstance(Protocol.dummy_protocol, Protocol)

    def test_user_manager_dispose(self):
        user = MagicMock()
        self.house._user_by_id = {"123": user}

        self.house.dispose()

        user.dispose.assert_called_once()
        self.assertEqual(self.house._user_by_id, {})
        self.assertEqual(self.house._is_restoring_now, False)
        self.assertIsNone(self.house.house_config)

    def test_on_player_connected(self):
        self.assertEqual(self.house.users_online, 0)
        self.assertEqual(self.house.players_online, 0)
        self.assertEqual(self.house.players_connected, 0)
        self.assertEqual(self.house.house_model.players_online, self.house.players_online)

        # OK with protocol
        auth_sig = GameService.make_auth_sig("123", "token1", "my_secret")
        player1 = self.house.on_player_connected(Mock(), "123", "token1", auth_sig, "test")
        # Wrong token
        auth_sig = GameService.make_auth_sig("123", "token2", "my_secret")
        player2 = self.house.on_player_connected(Mock(), "123", "token2_WRONG", auth_sig, "test")
        # OK without protocol
        auth_sig = GameService.make_auth_sig("456", "token3", "my_secret")
        player3 = self.house.on_player_connected(None, "456", "token3", auth_sig, "test")
        # Doesn't work with empty app_secret
        auth_sig = GameService.make_auth_sig("456", "token3", "")
        player4 = self.house.on_player_connected(None, "456", "token3", auth_sig)

        self.assertIsNone(player2)
        self.assertIsNone(player4)
        self.assertEqual(player1.user.user_id, "123")
        self.assertEqual(player3.user.user_id, "456")
        self.assertEqual(self.house.users_online, 2)
        self.assertEqual(self.house.players_online, 2)
        self.assertEqual(self.house.players_connected, 1)
        self.assertEqual(self.house.house_model.players_online, self.house.players_online)

    def test_on_player_disconnected(self):
        # OK with protocol
        auth_sig = GameService.make_auth_sig("123", "token1", "my_secret")
        player1 = self.house.on_player_connected(Mock(), "123", "token1", auth_sig, "test")
        player1.game = Mock()
        # OK without protocol
        auth_sig = GameService.make_auth_sig("456", "token3", "my_secret")
        player2 = self.house.on_player_connected(None, "456", "token3", auth_sig, "test")

        self.assertEqual(player1.user.user_id, "123")
        self.assertEqual(player2.user.user_id, "456")
        self.assertEqual(self.house.users_online, 2)
        self.assertEqual(self.house.players_online, 2)
        self.assertEqual(self.house.players_connected, 1)
        self.assertIsNotNone(player1.user)
        self.assertIsNotNone(player2.user)

        self.house.on_player_disconnected(player1)
        self.house.on_player_disconnected(player2)

        self.assertEqual(self.house.users_online, 1)
        self.assertEqual(self.house.players_online, 1)
        self.assertEqual(self.house.players_connected, 0)
        self.assertEqual(self.house.house_model.players_online, self.house.players_online)
        self.assertIsNotNone(player1.user)
        self.assertIsNone(player2.user)

    def test_retrieve_user(self):
        self.assertEqual(self.house.users_online, 0)

        # Create new
        user = self.house._retrieve_user("123")

        self.assertEqual(self.house.users_online, 0)
        self.assertIsInstance(user, User)
        self.assertEqual(user.user_id, "123")
        self.assertEqual(user.house_config, self.house.house_config)

        # Create new again
        user2 = self.house._retrieve_user("123")

        self.assertEqual(self.house.users_online, 0)
        self.assertNotEqual(user2, user)

        # Get previously created
        self.house._add_user(user)
        user3 = self.house._retrieve_user("123")

        self.assertEqual(self.house.users_online, 1)
        self.assertEqual(user3, user)

    def test_get_user(self):
        self.assertEqual(self.house.users_online, 0)

        self.assertIsNone(self.house.get_user("123"))

        # Create new
        user = self.house._retrieve_user("123")

        self.assertEqual(self.house.get_user("123"), user)

    def test_add_remove_user(self):
        self.assertEqual(self.house.users_online, 0)
        self.assertEqual(self.house.players_online, 0)
        self.assertEqual(self.house.players_connected, 0)

        user = User(self.house.house_config, "123")
        player1 = Player()
        player1.lobby_id, player1.room_id, player1.place_index = "1", "2", 1
        player2 = Player()
        player2.lobby_id, player2.room_id, player2.place_index = "1", "3", -1
        player3 = Player(protocol=Mock())
        user.add_player(player1)
        user.add_player(player2)
        user.add_player(player3)

        self.house._add_user(user)

        self.assertEqual(self.house.users_online, 1)
        self.assertEqual(self.house.players_online, 3)
        self.assertEqual(self.house.players_connected, 1)
        self.assertEqual(user.house, self.house)
        # Assert goto_lobby
        # player1
        self.assertEqual(player1.lobby.lobby_id, "1")
        self.assertEqual(player1.room.room_id, "2")
        self.assertIsNotNone(player1.game)
        self.assertEqual(player1.place_index, 1)
        # player2
        self.assertEqual(player2.lobby.lobby_id, "1")
        self.assertEqual(player2.room.room_id, "3")
        self.assertIsNone(player2.game)
        # player2
        self.assertEqual(player3.lobby.lobby_id, "1")
        self.assertIsNone(player3.room)
        self.assertIsNone(player3.game)

        self.house.remove_user(user)

        self.assertEqual(self.house.users_online, 0)
        self.assertEqual(self.house.players_online, 0)
        self.assertEqual(self.house.players_connected, 0)
        self.assertIsNone(user.house)
        # ??
        # # player1
        # self.assertIsNone(player1.lobby)
        # self.assertIsNone(player1.room)
        # self.assertIsNone(player1.game)
        # self.assertEqual(player1.place_index, -1)
        # # player2
        # self.assertIsNone(player2.lobby)
        # self.assertIsNone(player2.room)
        # self.assertIsNone(player2.game)
        # # player2
        # self.assertIsNone(player3.lobby)
        # self.assertIsNone(player3.room)
        # self.assertIsNone(player3.game)

    def test_update_players_online(self):
        self.house._user_by_id = {"1": Mock(player_set=set([Mock(), Mock()]))}
        self.assertEqual(self.house.players_online, 2)
        self.assertEqual(self.house.house_model.players_online, 0)

        self.house._update_players_online()

        self.assertEqual(self.house.house_model.players_online, 2)


class TestLobbyManager:
    house = None

    def test_lobbies_data(self):
        # Getter
        data = self.house.lobbies_data

        self.assertEqual(len(data), 3)
        self.assertEqual(data["2"][0][1], "Lobby 2")

        # Setter
        self.assertEqual(self.house._lobby_by_id["2"].lobby_name, "Lobby 2")
        data["2"][0][1] = "New Lobby 2@#$"

        self.house.lobbies_data = data

        self.assertEqual(self.house._lobby_by_id["2"].lobby_name, "New Lobby 2@#$")

        # Setter only updates existing lobbies and doesn't create new ones
        self.house.dispose()
        self.assertEqual(len(self.house._lobby_by_id), 0)
        self.house.lobbies_data = data
        self.assertEqual(len(self.house._lobby_by_id), 0)
        self.assertEqual(len(self.house.lobbies_data), 0)

    def test_constructor(self):
        self.assertIsNotNone(self.house.house_config)
        self.assertIsNotNone(self.house.house_model)
        self.assertEqual(len(self.house._lobby_list), 3)
        self.assertEqual(len(self.house._lobby_by_id), 3)
        for lobby_id, lobby in self.house._lobby_by_id.items():
            self.assertIsInstance(lobby, Lobby)
            self.assertTrue(lobby in self.house._lobby_list)
            self.assertTrue(lobby.lobby_model in self.house.house_config.lobby_model_list)

    def test_lobby_manager_dispose(self):
        self.assertEqual(len(self.house._lobby_list), 3)
        self.assertEqual(len(self.house._lobby_by_id), 3)
        for lobby_id, lobby in self.house._lobby_by_id.items():
            lobby.dispose = Mock()

        self.house.dispose()

        self.assertIsNone(self.house.house_config)
        self.assertIsNone(self.house.house_model)
        for lobby_id, lobby in self.house._lobby_by_id.items():
            lobby.dispose.assert_called_once()
        self.assertEqual(len(self.house._lobby_list), 0)
        self.assertEqual(len(self.house._lobby_by_id), 0)

    def test_goto_lobby(self):
        player = Player()
        self.assertIsNone(player.lobby_id)
        self.assertIsNone(player.lobby)

        # Default lobby
        self.house.goto_lobby(player)

        self.assertEqual(player.lobby.lobby_id, "1")

        # Go to another lobby
        self.house.goto_lobby(player, "2")

        self.assertEqual(player.lobby.lobby_id, "2")

        # Default lobby - now it is the same lobby
        self.house.goto_lobby(player)

        self.assertEqual(player.lobby.lobby_id, "2")

    def test_goto_lobby_on_restore(self):
        player = Player()
        player.lobby_id = "2"
        player.room_id = "1"
        player.lobby_id = 3
        self.assertIsNone(player.lobby)
        self.assertIsNone(player.room)
        self.assertIsNone(player.game)

        # Default lobby
        self.house.goto_lobby(player)

        self.assertEqual(player.lobby.lobby_id, "2")
        self.assertEqual(player.room.room_id, "1")
        self.assertIsNotNone(player.game)

    def test_choose_default_lobby(self):
        result = self.house.choose_default_lobby(None)

        self.assertEqual(result, self.house._lobby_list[0])

    def test_get_lobby_info_list(self):
        player = Player()
        player.protocol = MagicMock()

        self.house.get_lobby_info_list(player)

        player.protocol.lobby_info_list.assert_called_once()
        house_id = player.protocol.lobby_info_list.call_args[0][0]
        lobby_info_list = player.protocol.lobby_info_list.call_args[0][1]
        self.assertEqual(house_id, self.house.house_model.house_id)
        self.assertEqual(len(lobby_info_list), 3)
        self.assertEqual(len(lobby_info_list[0]), 3)

    def test_send_message_in_room(self):
        player = Player()
        player.lobby = Mock()
        player.room = Mock()

        # (Chat)
        self.house.send_message(MessageType.MSG_TYPE_CHAT, "some text...", player, "345")

        player.lobby.send_message.assert_not_called()
        player.room.send_message.assert_called_once_with(MessageType.MSG_TYPE_CHAT, "some text...", player, "345")

        # (Public)
        player.room.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "some text...", player, "345")

        player.lobby.send_message.assert_not_called()
        player.room.send_message.assert_called_once_with(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "some text...", player, "345")

        # (Private)
        player.room.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text...", player, "345")

        player.lobby.send_message.assert_not_called()
        player.room.send_message.assert_called_once_with(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text...", player, "345")

        # (Mail)
        player.room.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_MAIL, "some text...", player, "345")

        player.lobby.send_message.assert_not_called()
        player.room.send_message.assert_not_called()
        # waiting for functionality...

    def test_send_message_in_lobby(self):
        player = Player()
        player.lobby = Mock()
        player.room = None

        # (Chat)
        self.house.send_message(MessageType.MSG_TYPE_CHAT, "some text...", player, "345")

        player.lobby.send_message.assert_called_once_with(MessageType.MSG_TYPE_CHAT, "some text...", player, "345")
        # player.room.send_message.assert_not_called()

        # (Public)
        player.lobby.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "some text...", player, "345")

        player.lobby.send_message.assert_called_once_with(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "some text...", player, "345")
        # player.room.send_message.assert_not_called()

        # (Private)
        player.lobby.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text...", player, "345")

        player.lobby.send_message.assert_called_once_with(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "some text...", player, "345")
        # player.room.send_message.assert_not_called()

        # (Mail)
        player.lobby.send_message.reset_mock()

        self.house.send_message(MessageType.MSG_TYPE_MAIL, "some text...", player, "345")

        player.lobby.send_message.assert_not_called()
        # player.room.send_message.assert_not_called()
        # waiting for functionality...


class TestSaveLoadHouseStateMixIn:
    dump_file_path = "dumps/server1_state_dump.json"

    house = None

    def test_try_save_house_state_on_change(self):
        self.house.save_house_state = Mock()

        # is restoring
        self.house.house_model.is_save_house_state_on_any_change = True
        self.house._is_restoring_now = True

        self.house.try_save_house_state_on_change()

        self.house.save_house_state.assert_not_called()

        # save on change disabled
        self.house.house_model.is_save_house_state_on_any_change = False
        self.house._is_restoring_now = False

        self.house.try_save_house_state_on_change()

        self.house.save_house_state.assert_not_called()

        # OK
        self.house.house_model.is_save_house_state_on_any_change = True
        self.house._is_restoring_now = False

        self.house.try_save_house_state_on_change()

        self.house.save_house_state.assert_called_once()

    def test_save_house_state(self):
        # Disabled
        self.house_model.is_save_house_state_enabled = False

        self.house.save_house_state()

        self.assertFalse(os.path.exists(self.dump_file_path))

        # OK
        self.house_model.is_save_house_state_enabled = True

        self.house.save_house_state()

        self.assertTrue(os.path.exists(self.dump_file_path))
        data = json.load(open(self.dump_file_path))
        self.assertEqual(len(data), 3)
        # ?--
        self.assertIsNotNone(data["model_data"])
        self.assertIsNotNone(data["lobbies_data"])
        self.assertIsNotNone(data["users_data"])

        # Tear down
        os.remove(self.dump_file_path)

    def test_restore_house_state(self):
        self.house.on_player_connected(Mock(), "123", "45678")
        self.house.save_house_state()

        self.house.house_model.house_name = "some_house_name@#$"
        self.house._lobby_by_id["2"].lobby_name = "some_lobby_name@#$"
        self.house._user_by_id["123"].social_id = "some_social_id@#$"

        self.house.restore_house_state()

        self.assertEqual(self.house.house_model.house_name, "server1")
        self.assertEqual(self.house._lobby_by_id["2"].lobby_name, "Lobby 2")
        self.assertEqual(self.house._user_by_id["123"].social_id, "45678")

        # Tear down
        os.remove(self.dump_file_path)

    def test_save_state(self):
        if os.path.exists("dumps/"):
            os.remove("dumps/")
        self.assertFalse(os.path.exists("dumps/"))
        self.assertFalse(os.path.exists(self.dump_file_path))

        self.house._save_state("server1", {"a": [1, 2], "b": "value"})

        self.assertTrue(os.path.exists("dumps/"))
        self.assertTrue(os.path.exists(self.dump_file_path))
        data = json.load(open(self.dump_file_path))
        self.assertEqual(data, {"a": [1, 2], "b": "value"})

        # Tear down
        os.remove(self.dump_file_path)

    def test_load_state(self):
        # Nothing to load
        if os.path.exists("dumps/"):
            os.remove("dumps/")
        self.assertFalse(os.path.exists("dumps/"))
        self.assertFalse(os.path.exists(self.dump_file_path))

        result = self.house._load_state("server1")

        self.assertIsNone(result)

        # OK
        self.house._save_state("server1", {"a": [1, 2], "b": "value"})

        result = self.house._load_state("server1")

        self.assertEqual(result, {"a": [1, 2], "b": "value"})

        # Tear down
        os.remove(self.dump_file_path)


class TestHouse(TestCase, TestLobbyManager, TestUserManager, TestSaveLoadHouseStateMixIn):

    house = None

    def setUp(self):
        super().setUp()

        house_config = HouseConfig(house_id=0, data_dir_path="initial_configs")
        self.house = House(house_config)

    def test_export_data(self):
        data = self.house.export_data()

        self.assertEqual(len(data), 3)
        # ?--
        self.assertIn("model_data", data)
        self.assertIn("lobbies_data", data)
        self.assertIn("users_data", data)

    def test_model_data(self):
        self.assertEqual(self.house.house_model.house_name, "server1")

        # Getter
        model_data = self.house.model_data

        self.assertGreater(len(model_data), 12)
        self.assertEqual(model_data[1], "server1")

        # Setter
        model_data[1] = "another_server_name@#$"

        self.house.model_data = model_data

        self.assertEqual(self.house.house_model.house_name, "another_server_name@#$")

    def test_constructor(self):
        TestLobbyManager.test_constructor(self)
        TestUserManager.test_constructor(self)
        # TestSaveLoadHouseStateMixIn.test_constructor(self)

        self.assertIsNotNone(self.house.house_config)
        self.assertIsNotNone(self.house.house_model)
        self.assertEqual(self.house.house_config.house_model, self.house.house_model)
        self.assertIsNotNone(self.house.logging)

    def test_dispose(self):
        self.house.dispose()

        self.assertIsNone(self.house.house_config)
        self.assertIsNone(self.house.house_model)
        self.assertIsNone(self.house.logging)

    def test_start(self):
        self.house.restore_house_state = Mock()

        # Restoring disabled
        self.house.house_model.is_restore_house_state_on_start = False

        self.house.start()

        self.house.restore_house_state.assert_not_called()

        # OK
        self.house.house_model.is_restore_house_state_on_start = True

        self.house.start()

        self.house.restore_house_state.assert_called_once()

    def test_stop(self):
        # Empty
        pass


class TestHouseModel(TestCase):
    # See test_core.py

    def test_properties(self):
        properties = ["house_id", "house_name", "host", "port", "lobbies", "default_lobby_id", "is_allow_guest_auth",
                      "is_allow_multisession", "is_allow_multisession_in_the_room", "is_save_house_state_enabled",
                      "is_save_house_state_on_any_change", "is_restore_house_state_on_start",
                      "is_continue_on_disconnect"]

        house_model = HouseModel(properties)
        house_model.players_online = 1234

        for property in properties:
            self.assertEqual(getattr(house_model, property), property)
        self.assertEqual(house_model.export_data(), properties)
        self.assertEqual(house_model.export_public_data(), ["house_id", "house_name", "host", "port", 1234])

    def test_on_reload(self):
        # on_relaod from constructor
        house_config = HouseConfig(house_id=0, data_dir_path="initial_configs")
        # house_model = HouseModel()
        house_model = house_config.house_model

        self.assertEqual(house_model.lobbies, ["1", "2", "3"])
        self.assertEqual([model.id for model in house_model.lobby_model_list], ["1", "2", "3"])
        self.assertEqual(len(house_model.lobby_model_by_id), 3)

        # on_relaod
        house_model.default_lobby_id = "100"
        LobbyModel.get_model_by_id("2").room_name = "Lobby 2 changed"
        self.assertEqual(house_model.lobby_model_by_id["1"].lobby_name, "Lobby 1")
        self.assertEqual(house_model.lobby_model_by_id["2"].lobby_name, "Lobby 2")
        self.assertEqual(len(house_model.lobby_model_by_id), 3)
        self.assertNotIn("55", house_model.lobby_model_by_id)

        house_model.on_reload({"lobbies": [[1, "Lobby 1 changed"], ["2"], ["55", "Lobby 55"]]})

        self.assertEqual(house_model.lobby_model_by_id["1"].lobby_name, "Lobby 1 changed")
        self.assertEqual(house_model.lobby_model_by_id["2"].lobby_name, "Lobby 2 changed")
        self.assertEqual(len(house_model.lobby_model_by_id), 4)
        self.assertIn("55", house_model.lobby_model_by_id)
        self.assertEqual(house_model.default_lobby_id, -1)


class TestHouseConfig(TestCase):
    # See also test_core.py

    def test_constructor(self):
        # Empty
        HouseModel.dispose_models()

        house_config = HouseConfig()

        self.assertEqual(house_config.house_id, "0")
        self.assertEqual(house_config._data_dir_path, "")
        self.assertEqual(house_config._backend_info_by_backend, {})
        self.assertEqual(house_config.house_model, None)

        # Real
        house_config = HouseConfig("myhost", "myport", 0, data_dir_path="initial_configs",
                                   game_config_model_class=PokerGameConfigModel,
                                   room_model_class=PokerRoomModel,
                                   lobby_model_class=MyLobbyModel,
                                   house_model_class=MyHouseModel,
                                   room_class=PokerRoom)

        self.assertEqual(house_config.host, "myhost")
        self.assertEqual(house_config.port, "myport")
        self.assertEqual(house_config.house_id, "0")
        # Set by kwargs
        self.assertEqual(house_config.room_class, PokerRoom)
        self.assertEqual(house_config.game_config_model_class, PokerGameConfigModel)
        self.assertEqual(GameConfigModel.model_class, PokerGameConfigModel)
        self.assertEqual(RoomModel.model_class, PokerRoomModel)
        self.assertEqual(LobbyModel.model_class, MyLobbyModel)
        self.assertEqual(HouseModel.model_class, MyHouseModel)
        # Loaded
        self.assertNotEqual(house_config._backend_info_by_backend["test"], {"app_secret": "my_secret"})
        self.assertNotEqual(house_config.get_backend_info("temp"), {"some": "for_test_value"})
        self.assertNotEqual(house_config.house_model.house_id, "0")

    def test_dispose(self):
        house_config = HouseConfig(data_dir_path="initial_configs")
        self.assertGreater(len(GameConfigModel.model_list), 0)
        self.assertGreater(len(RoomModel.model_list), 0)
        self.assertGreater(len(LobbyModel.model_list), 0)
        self.assertGreater(len(HouseModel.model_list), 0)
        self.assertGreater(len(house_config._backend_info_by_backend), 0)
        house_config.house_model.dispose = Mock()

        house_config.dispose()

        self.assertEqual(len(GameConfigModel.model_list), 0)
        self.assertEqual(len(RoomModel.model_list), 0)
        self.assertEqual(len(LobbyModel.model_list), 0)
        self.assertEqual(len(HouseModel.model_list), 0)
        self.assertEqual(len(house_config._backend_info_by_backend), 0)
        house_config.house_model.dispose.assert_called_once()
        self.assertIsNone(house_config.house_model)
        self.assertIsNone(house_config.logging)

    def test_reload(self):
        house_config = HouseConfig(data_dir_path="initial_configs")
        self.assertEqual(house_config.get_backend_info("temp"), {"some": "for_test_value"})
        self.assertEqual(house_config.house_model.lobby_model_by_id["1"].lobby_name, "Lobby 1")
        self.assertEqual(len(house_config.house_model.lobby_model_by_id), 3)

        house_config._data_dir_path = "changed_configs"
        house_config.reload()

        self.assertEqual(house_config.get_backend_info("temp"), None)
        self.assertEqual(house_config.house_model.lobby_model_by_id["1"].lobby_name, "Lobby 1 changed")
        # ?
        self.assertEqual(len(house_config.house_model.lobby_model_by_id), 3)

    def test_get_backend_info(self):
        house_config = HouseConfig()

        self.assertEqual(house_config.get_backend_info("test"), None)

        house_config = HouseConfig(data_dir_path="initial_configs")

        self.assertEqual(house_config.get_backend_info("test"), {"app_secret": "my_secret"})
        # Resolve item
        self.assertEqual(house_config.get_backend_info("temp"), {"some": "for_test_value"})

    def test_load_json(self):
        house_config = HouseConfig()

        result = house_config._load_json("initial_configs/rooms.json")

        self.assertIsInstance(result, dict)
        self.assertIn("extra1", result)
