import time
from unittest import TestCase
from unittest.mock import Mock, call

from napalm.async import AbstractTimer
from napalm.play.core import HouseConfig
from napalm.play.game import Game, GameConfigModel
from napalm.play.game_ext import TournamentGame
from napalm.play.house import House
from napalm.play.protocol import MessageCode
from napalm.play.test import utils
from napalm.play.test.test_lobby import Asserts
from napalm.test.test_async import BaseTestTimer


# MODEL

class MyGameConfigModel(GameConfigModel):
    param1 = None
    param2 = None
    param3 = None
    param4 = None

    @property
    def _config_property_names(self):
        return ["id", "param1", "param2", "param3", "param4"]


class TestGameConfigModelPropertiesMixIn:
    assertEqual = None

    _model_class = GameConfigModel

    def _create_model(self):
        model = self._model_class()
        # model. =
        # model. =
        # model. =
        # model. =
        # model. =
        return model

    def _create_expected_data(self):
        return []

    def test_properties(self):
        model = self._create_model()
        expected_data = self._create_expected_data()

        data = model.export_data()
        self.assertEqual(data, expected_data)

        model.import_data(model.export_data())
        self.assertEqual(model.export_data(), data)


class TestGameConfigModel(TestCase, TestGameConfigModelPropertiesMixIn):
    house_config = None

    def setUp(self):
        # TestGameConfigModelPropertiesMixIn.setUp(self)

        self.house_config = HouseConfig(data_dir_path="initial_configs/")

    def test_constructor(self):
        # Normal
        model = MyGameConfigModel(["01", "02", "03", "04"], [1, "H", 55])

        self.assertIsNone(model.id)
        self.assertEqual(model.ids, [1, "H", 55])
        self.assertEqual(model.export_data(), [None, "value401", "value402", "valueH3", "04"])

        # Empty
        model = MyGameConfigModel()

        self.assertIsNone(model.id)
        self.assertEqual(model.ids, [])
        self.assertEqual(model.export_data(), [None, None, None, None, None])

    def test_game_configs_workflow(self):
        # Model as combination of other models
        model = MyGameConfigModel.create_multimodel_by_ids([1, "H", "40"])

        self.assertIsNone(model.id)
        self.assertEqual(model.export_data(), [None, "value401", "value402", "valueH3", "value04"])

        # Reset
        model.param1 = "my_value1"

        self.assertEqual(model.export_data(), [None, "my_value1", "value402", "valueH3", "value04"])

        model.reset()

        self.assertEqual(model.export_data(), [None, "value401", "value402", "valueH3", "value04"])

        # Change ids (change order, add new id, remove old one)
        model.ids = [40, "H", "OH"]

        self.assertEqual(model.export_data(), [None, "valueOH1", "value402", "valueH3", "valueOH4"])

        # Reset
        model.import_data(["my_value1"])

        self.assertEqual(model.export_data(), [None, "my_value1", "value402", "valueH3", "valueOH4"])

        model.reset()

        self.assertEqual(model.export_data(), [None, "valueOH1", "value402", "valueH3", "valueOH4"])

        # Submodels changed
        self.house_config._data_dir_path = "changed_configs"
        self.house_config.reload()

        self.assertEqual(model.export_data(), [None, "valueOH1", "value402", "valueH3", "valueOH4"])  # not changed

        model.apply_changes()

        self.assertEqual(model.export_data(), [None, "valueOH1", "value__402", "value__H3", "valueOH4"])  # changed

        model.reset()

        self.assertEqual(model.export_data(), [None, None, "value__402", "value__H3", None])  # changed

        # Set empty ids
        model.ids = []

        self.assertEqual(model.export_data(), [None, None, "value__402", "value__H3", None])  # not changed

        model.apply_changes()

        self.assertEqual(model.export_data(), [None, None, "value__402", "value__H3", None])  # not changed

        model.reset()

        self.assertEqual(model.export_data(), [None, None, None, None, None])


# GAME

class TestGamePlayerManagerMixIn(Asserts):
    house_config = None
    game_class = None

    room1 = None
    room2 = None
    room3 = None
    player1 = None
    player2 = None
    player3 = None

    def test_max_playing_count(self):
        self.assertEqual(self.room1.max_player_count, 9)
        self.assertEqual(self.room2.max_player_count, 6)

    def test_player_by_place_index_list(self):
        self.assertEqual(self.room1.game.player_by_place_index_list, [
            self.player1, None, None, self.player2, None, None, None, None, None])
        self.assertEqual(self.room2.game.player_by_place_index_list, [None] * 6)

    def test_init(self):
        game = self.game_class()

        self.assertEqual(game.player_list, [])
        self.assertEqual(game._player_by_place_index, {})
        self.assertEqual(game._player_by_place_index_list, None)
        self.assertEqual(game._ready_to_start_players, [])

        return game

    def test_dispose(self):
        self.assertEqual(len(self.room1.game.player_list), 2)
        self.assertEqual(len(self.room1.game._player_by_place_index), 2)

        self.room1.game.dispose()

        self.assertEqual(self.room1.game.player_list, [])
        self.assertEqual(self.room1.game._player_by_place_index, {})
        self.assertEqual(self.room1.game._player_by_place_index_list, None)
        self.assertEqual(self.room1.game._ready_to_start_players, [])

    def test_players_in_game_workflow(self):
        self.room1.send_player_joined_the_game = Mock()
        self.room1.send_player_left_the_game = Mock()
        self.room1.send_log = Mock()

        self.assertEqual(len(self.room1.game.player_list), 2)
        self.room1.game._remove_all_players()
        self.assertEqual(len(self.room1.game.player_list), 0)
        self.assertEqual(self.room1.game, None)

        # Add first
        self.assertEqual(self.player1.game, None)
        self.assertEqual(self.player1.place_index, -1)
        self.assertEqual(self.player1.money_in_play, 0)
        self.assertEqual(self.player1.money_amount, 20000)

        # (Cannot call game.add_player because game is None)
        result = self.room1.join_the_game(self.player1, 1, 10000)

        self.assertTrue(result)
        self.assertEqual(self.room1.game.player_by_place_index_list[1], self.player1)
        self.assertEqual(self.player1.game, self.room1.game)
        self.assertEqual(self.player1.place_index, 1)
        self.assertEqual(self.player1.money_in_play, 10000)
        self.assertEqual(self.player1.money_amount, 10000)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 1)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player1)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_called_once()
        self.room1.send_log.reset_mock()

        # Add again (on rebuy - with params)
        result = self.room1.game.add_player(self.player1, 2, 5000)

        self.assertTrue(result)
        self.assertEqual(self.player1.place_index, 2)
        self.assertEqual(self.player1.money_in_play, 15000)
        self.assertEqual(self.player1.money_amount, 5000)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player1)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_not_called()

        # Add again (on reconnect - without params)
        result = self.room1.game.add_player(self.player1)

        self.assertTrue(result)
        self.assertEqual(self.player1.place_index, 2)
        self.assertEqual(self.player1.money_in_play, 15000)
        self.assertEqual(self.player1.money_amount, 5000)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player1)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_not_called()

        # Check can be added
        self.assertFalse(self.room1.game.can_be_added(self.player2))
        self.assertTrue(self.room1.game.can_be_added(self.player2, money_in_play=500))
        self.assertFalse(self.room1.game.can_be_added(self.player2, 1))
        self.assertTrue(self.room1.game.can_be_added(self.player2, 0))
        self.assertFalse(self.room1.game.can_be_added(self.player2, 0, 100))
        self.assertTrue(self.room1.game.can_be_added(self.player2, 0, 500))

        # Add second
        result = self.room1.game.add_player(self.player2)
        self.assertFalse(result)
        result = self.room1.game.add_player(self.player2, money_in_play=100)
        self.assertFalse(result)
        self.assertEqual(self.room1.game.player_list, [self.player1])

        result = self.room1.game.add_player(self.player2, money_in_play=500)
        self.assertTrue(result)
        # (player_list also sorted)
        self.assertEqual(self.room1.game.player_list, [self.player1, self.player2])
        self.assertEqual(self.room1.game._player_by_place_index, {1: self.player1, 0: self.player2})

        # Full the game with mocks (3-9)
        for i in range(3, 9):
            self.room1.game.add_player(Mock(), money_in_play=5500)
        self.assertEqual(len(self.room1.game.player_list), self.room1.max_player_count)

        # Add to full game
        result = self.room1.game.add_player(self.player3, money_in_play=5500)

        self.assertFalse(result)
        self.assertFalse(self.room1.game.can_be_added(self.player3, -1, 5000))

        # Remove
        self.room1.game._check_end_game = Mock()

        result = self.room1.game.remove_player(self.player1)

        self.assertTrue(result)
        self.assertEqual(self.player1.game, None)
        self.assertEqual(self.player1.place_index, -1)
        self.assertEqual(self.player1.money_in_play, 0)
        self.assertEqual(self.player1.money_amount, 20000)
        self.assertEqual(len(self.room1.game.player_list), 8)
        self.assertEqual(len(self.room1.game._player_by_place_index), 8)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 8)
        self.room1.send_player_left_the_game.assert_called_once_with(self.player1)
        self.room1.send_log.assert_called_once()
        self.room1.game._check_end_game.assert_called_once()

        # Remove again
        result = self.room1.game.remove_player(self.player1)

        self.assertFalse(result)

        # Game became not full
        self.assertTrue(self.room1.game.can_be_added(self.player3, -1, 5000))

    def test_can_be_added(self):
        self.assertTrue(self.room1.game.game_config_model.is_find_free_place_if_specified_one_taken)
        # min_buy_in==500
        self.assertFalse(self.room1.game.can_be_added(self.player1))
        self.assertTrue(self.room1.game.can_be_added(self.player1, money_in_play=500))
        # max_buy_in not checked, only slice the resulting money_in_play
        self.assertTrue(self.room1.game.can_be_added(self.player1, money_in_play=5000000))
        # min_buy_in==0
        self.assertFalse(self.room2.game.can_be_added(self.player1))

        # place_index already used
        self.assertTrue(self.room1.game.can_be_added(self.player1, 0, 500))  # not free
        self.assertTrue(self.room1.game.can_be_added(self.player1, 2, 500))  # free
        self.assertTrue(self.room1.game.can_be_added(self.player1, -1, 500))  # find free

        # (is_find_free_place_if_specified_one_taken==False)
        self.assertFalse(self.room2.game.game_config_model.is_find_free_place_if_specified_one_taken)
        self.assertTrue(self.room2.game.can_be_added(self.player1, 2, 500))  # free
        self.player2.room.remove_player(self.player2)
        self.room2.add_player(self.player2)
        self.room2.join_the_game(self.player2, place_index=2, money_in_play=1000)
        self.assertFalse(self.room2.game.can_be_added(self.player1, 2, 500))  # not free
        self.assertTrue(self.room2.game.can_be_added(self.player1, 3, 500))  # free
        self.assertTrue(self.room2.game.can_be_added(self.player1, -1, 500))  # find free

        # max_player_count==9
        for i in range(2, 9):
            # player = Mock(first_name="", last_name="", money_in_play=1000)
            player = utils.create_some_player(self.house_config)
            self.room1.add_player(player)
            self.room1.join_the_game(player, money_in_play=1000)
        self.assertTrue(self.room1.game.can_be_added(self.player1, -1, 500))
        # player = Mock(first_name="", last_name="", money_in_play=1000)
        player = utils.create_some_player(self.house_config)
        self.room1.add_player(player)
        self.room1.join_the_game(player, money_in_play=1000)
        self.assertFalse(self.room1.game.can_be_added(self.player1, -1, 500))

        # is_join_only_between_games==True (min_buy_in==0)
        self.assertTrue(self.room2.room_model.game_config_model.is_join_only_between_games)
        self.assertFalse(self.room2.game.is_tournament)
        self.assertTrue(self.room2.game.can_be_added(self.player1, money_in_play=500))
        self.room2.game._is_in_progress = True
        self.assertFalse(self.room2.game.can_be_added(self.player1, money_in_play=500))

        # is_tournament==True (min_buy_in==0)
        self.assertFalse(self.room3.room_model.game_config_model.is_join_only_between_games)
        self.assertTrue(self.room3.game.is_tournament)
        self.assertTrue(self.room3.game.can_be_added(self.player1, money_in_play=5000))
        self.room3.game._is_tournament_in_progress = True
        self.assertFalse(self.room3.game.can_be_added(self.player1, money_in_play=5000))

    def test_add_player(self):
        self.room1.send_player_joined_the_game = Mock()
        self.room1.send_player_left_the_game = Mock()
        self.room1.send_log = Mock()
        self.room1.game._on_add_player = Mock()
        self.player3.protocol.show_ok_message_dialog = Mock()

        # Try to add (don't fit min_buy_in)
        result = self.room1.game.add_player(self.player3, 1, 100)

        self.assertFalse(result)
        self.assertEqual(self.player3.game, None)
        self.assertEqual(self.player3.place_index, -1)
        self.assertEqual(self.player3.money_in_play, 0)
        self.assertEqual(self.player3.money_amount, 20000)
        self.assertEqual(len(self.room1.game.player_list), 2)
        self.player3.protocol.show_ok_message_dialog.assert_called_once_with(
            MessageCode.JOIN_GAME_FAIL_TITLE, MessageCode.JOIN_GAME_FAIL)
        self.room1.send_player_joined_the_game.assert_not_called()
        self.room1.send_log.assert_not_called()
        self.room1.game._on_add_player.assert_not_called()

        # Add
        result = self.room1.game.add_player(self.player3, 1, 10000)

        self.assertTrue(result)
        self.assertEqual(self.room1.game.player_by_place_index_list[2], self.player3)
        self.assertEqual(self.player3.game, self.room1.game)
        self.assertEqual(self.player3.place_index, 2)
        self.assertEqual(self.player3.money_in_play, 10000)
        self.assertEqual(self.player3.money_amount, 10000)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 3)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player3)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_called_once()
        self.room1.send_log.reset_mock()
        self.room1.game._on_add_player.assert_called_once_with(self.player3)
        self.room1.game._on_add_player.reset_mock()

        # Add again (on rebuy - with params)
        result = self.room1.game.add_player(self.player3, 3, 5000)

        self.assertTrue(result)
        self.assertEqual(self.room1.game.player_by_place_index_list[2], None)
        self.assertEqual(self.room1.game.player_by_place_index_list[3], self.player3)
        self.assertEqual(self.player3.is_playing, False)
        self.assertEqual(self.player3.place_index, 3)
        self.assertEqual(self.player3.money_in_play, 15000)
        self.assertEqual(self.player3.money_amount, 5000)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player3)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_not_called()
        self.room1.game._on_add_player.assert_not_called()

        # Add again (on reconnect - without params)
        result = self.room1.game.add_player(self.player3)

        self.assertTrue(result)
        self.room1.send_player_joined_the_game.assert_called_once_with(self.player3)
        self.room1.send_player_joined_the_game.reset_mock()
        self.room1.send_log.assert_not_called()
        self.room1.game._on_add_player.assert_not_called()

    def test_remove_player(self):
        self.room1.send_player_left_the_game = Mock()
        self.room1.send_log = Mock()
        self.room1.game._on_remove_player = Mock()
        self.room1.game._check_end_game = Mock()

        # Not added
        result = self.room1.game.remove_player(self.player3)

        self.room1.send_player_left_the_game.assert_not_called()
        self.room1.send_log.assert_not_called()
        self.room1.game._check_end_game.assert_not_called()

        # OK
        self.assertEqual(self.player1.game, self.room1.game)
        self.assertEqual(self.player1.place_index, 0)
        self.assertEqual(self.player1.money_in_play, 10000)
        self.assertEqual(self.player1.money_amount, 10000)
        self.assertEqual(len(self.room1.game.player_list), 2)
        self.assertEqual(len(self.room1.game._player_by_place_index), 2)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 2)

        result = self.room1.game.remove_player(self.player1)

        self.assertTrue(result)
        self.assertEqual(self.player1.game, None)
        self.assertEqual(self.player1.place_index, -1)
        self.assertEqual(self.player1.money_in_play, 0)
        self.assertEqual(self.player1.money_amount, 20000)
        self.assertEqual(len(self.room1.game.player_list), 1)
        self.assertEqual(len(self.room1.game._player_by_place_index), 1)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 1)
        self.room1.send_player_left_the_game.assert_called_once_with(self.player1)
        self.room1.send_player_left_the_game.reset_mock()
        self.room1.send_log.assert_called_once()
        self.room1.send_log.reset_mock()
        self.room1.game._check_end_game.assert_called_once()
        self.room1.game._check_end_game.reset_mock()

        # Remove again
        result = self.room1.game.remove_player(self.player1)

        self.assertFalse(result)
        self.room1.send_player_left_the_game.assert_not_called()
        self.room1.send_log.assert_not_called()
        self.room1.game._check_end_game.assert_not_called()

    def test_remove_all_players(self):
        self.room1.send_player_left_the_game = Mock()
        self.room1.send_log = Mock()
        self.room1.game._on_remove_player = Mock()
        self.room1.game._check_end_game = Mock()

        self.assertEqual(self.player1.game, self.room1.game)
        self.assertEqual(self.player1.place_index, 0)
        self.assertEqual(self.player1.money_in_play, 10000)
        self.assertEqual(self.player1.money_amount, 10000)
        self.assertEqual(len(self.room1.game.player_list), 2)
        self.assertEqual(len(self.room1.game._player_by_place_index), 2)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 2)

        self.room1.game._remove_all_players()

        self.assertEqual(self.player1.game, None)
        self.assertEqual(self.player1.place_index, -1)
        self.assertEqual(self.player1.money_in_play, 0)
        self.assertEqual(self.player1.money_amount, 20000)
        self.assertEqual(len(self.room1.game.player_list), 0)
        self.assertEqual(len(self.room1.game._player_by_place_index), 0)
        self.assertEqual(len(self.room1.game.player_by_place_index_list), 9)
        self.assertEqual(len([p for p in self.room1.game.player_by_place_index_list if p is not None]), 0)
        self.assertEqual(self.room1.send_player_left_the_game.call_count, 2)
        self.assertEqual(self.room1.send_log.call_count, 2)
        self.assertEqual(self.room1.game._on_remove_player.call_count, 2)
        self.assertEqual(self.room1.game._check_end_game.call_count, 2)

    def test_on_add_and_remove_player(self):
        self.room1.game._on_add_player = Mock()
        self.room1.game._on_remove_player = Mock()
        self.room2.game._on_remove_player = Mock()

        # Add
        # Not called
        self.room1.game.add_player(self.player1, -1, 10000)

        self.room1.game._on_add_player.assert_not_called()

        # Called
        self.room1.game.add_player(self.player3, -1, 10000)

        self.room1.game._on_add_player.assert_called_once_with(self.player3)

        # Remove
        # Not called
        self.room2.game.remove_player(self.player1)

        self.room2.game._on_remove_player.assert_not_called()

        # Called
        self.room1.game.remove_player(self.player3)

        self.room1.game._on_remove_player.assert_called_once_with(self.player3)

    def test_find_free_place_index(self):
        # [x, x, 0, 0, 0, 0, 0, 0, 0]
        self.assertEqual(self.room1.game._find_free_place_index(), 2)

        # [0, x, 0, 0, 0, 0, 0, 0, 0]
        self.room1.game.remove_player(self.player1)

        self.assertEqual(self.room1.game._find_free_place_index(), 0)

        self.room1.game.add_player(self.player1)
        self.room1.game.remove_player(self.player2)

        self.assertEqual(self.room1.game._find_free_place_index(), 1)

        # [x, x, x, x, x, x, x, x, x]
        # max_player_count==9
        for i in range(1, 9):
            self.room1.join_the_game(Mock(), money_in_play=1000)

        self.assertEqual(self.room1.game._find_free_place_index(), -1)

        # Rough
        # [x, x, x, x, 0, x, x, x, x]
        del self.room1.game._player_by_place_index[4]

        self.assertEqual(self.room1.game._find_free_place_index(), 4)

    def test_find_nearest_player_to(self):
        # [x, x (playing), 0, 0, 0, x (no money), 0, 0, 0]
        self.player2.is_playing = True
        self.room1.join_the_game(self.player3, 5, 500)
        self.player3.money_in_play = 0

        self.assertEqual(self.room1.game._find_nearest_player_to(2), 1)
        self.assertEqual(self.room1.game._find_nearest_player_to(1), 1)
        self.assertEqual(self.room1.game._find_nearest_player_to(1, is_check_playing=False), 0)
        self.assertEqual(self.room1.game._find_nearest_player_to(1, False), 0)
        self.assertEqual(self.room1.game._find_nearest_player_to(1, is_money_in_play=False), 5)
        self.assertEqual(self.room1.game._find_nearest_player_to(1, False, False), 5)
        self.assertEqual(self.room1.game._find_nearest_player_to(5, False, False), 0)


class TestGame(TestCase, TestGamePlayerManagerMixIn):

    game_class = TournamentGame
    game_config_model_class = GameConfigModel
    data_dir_path = "game_configs/"

    DELAY_SEC = BaseTestTimer.DELAY_SEC
    DELAY_BEFORE_SEC = BaseTestTimer.delay_before()
    BETWEEN_BEFORE_AND_AFTER_SEC = BaseTestTimer.between_before_and_after()
    assertEqualRound = BaseTestTimer.assertEqualRound

    house_config = None
    house = None
    lobby = None
    room1 = None
    room2 = None
    room3 = None

    user1 = None
    player1 = None
    user2 = None
    player2 = None
    player3 = None
    player4 = None

    def setUp(self):
        # TestGamePlayerManagerMixIn.setUp(self)

        AbstractTimer.resolution_sec = BaseTestTimer.RESOLUTION_SEC

        self.house_config = HouseConfig(data_dir_path=self.data_dir_path)
        self.house_config.game_class = self.game_class
        self.house_config.game_config_model_class = self.game_config_model_class
        self.house = House(self.house_config)
        self.lobby = self.house._lobby_by_id["1"]
        self.room1 = self.lobby.room_by_id["1"]
        self.room2 = self.lobby.room_by_id["2"]
        self.room3 = self.lobby.room_by_id["4"]
        self.room1.room_model.between_rounds_delay_sec = self.DELAY_SEC
        self.room2.room_model.between_rounds_delay_sec = self.DELAY_SEC
        self.room3.room_model.between_rounds_delay_sec = self.DELAY_SEC

        self.user1 = utils.create_user(self.house_config, "123", 20000)
        self.player1 = utils.create_player(self.user1, lobby=self.lobby)  # Connected, not added to lobby
        self.user2 = utils.create_user(self.house_config, "456", 20000)
        self.player2 = utils.create_player(self.user2, False, self.lobby)  # Not connected, not added
        self.user3 = utils.create_user(self.house_config, "789", 20000)
        self.player3 = utils.create_player(self.user3, True, self.lobby)  # Connected, not added
        self.player4 = utils.create_player(self.user3, True, self.lobby)  # Connected, not added

        self.room1.add_player(self.player1)
        self.room1.add_player(self.player2)
        self.room1.join_the_game(self.player1, money_in_play=1000)
        self.room1.join_the_game(self.player2, 3, money_in_play=1000)
        # (Join the rooms to create "game" instance in room)
        self.room1.add_player(Mock())
        self.room2.add_player(Mock())
        self.room3.add_player(Mock())

    # def tearDown(self):
    #     TestGamePlayerManagerMixIn.tearDown(self)

    @property
    def default_property_values(self):
        return ["1", False, False, 0]

    @property
    def change_property_values(self):
        return ["2", True, True, 2]

    def test_export_import(self):
        self.assertEqual(self.room1.game.export_data(), self.default_property_values)

        self.room1.game.import_data(self.change_property_values)

        self.assertEqual(self.room1.game.room_id, "1")
        self.assertEqual(self.room1.game._is_in_progress, False)
        self.assertEqual(self.room1.game._is_paused, True)
        self.assertEqual(self.room1.game.game_elapsed_time, 2)

    def test_public_export_import(self):
        # Assert that public export/import is the same as not public

        self.assertEqual(self.room1.game.public_export_data(), self.default_property_values)

        self.room1.game.import_data(self.change_property_values)

        self.assertEqual(self.room1.game.public_export_data(), self.room1.game.export_data())

    def test_properties(self):
        self.assertEqual(self.room1.game.room_id, "1")

        self.room1.game.game_elapsed_time = 11
        self.assertEqual(self.room1.game.game_elapsed_time, 11)

    def test_is_paused(self):
        # Unit tests

        self.room1.game._is_paused = True
        self.room1.game._is_resuming_pause = True

        self.assertTrue(self.room1.game.is_paused)

        self.room1.game._is_paused = True
        self.room1.game._is_resuming_pause = False

        self.assertTrue(self.room1.game.is_paused)

        self.room1.game._is_paused = False
        self.room1.game._is_resuming_pause = True

        self.assertTrue(self.room1.game.is_paused)

        self.room1.game._is_paused = False
        self.room1.game._is_resuming_pause = False

        self.assertFalse(self.room1.game.is_paused)

        # System tests

        self.room1.room_model.resume_game_countdown_sec = self.DELAY_SEC

        self.assertFalse(self.room1.game.is_paused)
        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game._is_resuming_pause)

        # Pause
        self.room1.game.pause_game()

        self.assertTrue(self.room1.game.is_paused)
        self.assertTrue(self.room1.game._is_paused)
        self.assertFalse(self.room1.game._is_resuming_pause)

        # Resume
        self.room1.game.resume_game()

        self.assertTrue(self.room1.game.is_paused)
        self.assertFalse(self.room1.game._is_paused)
        self.assertTrue(self.room1.game._is_resuming_pause)

        # Still resuming...
        time.sleep(self.DELAY_BEFORE_SEC)
        self.assertTrue(self.room1.game._is_resuming_pause)

        # Resumed
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)
        self.assertFalse(self.room1.game.is_paused)
        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game._is_resuming_pause)

    def test_start_countdown_sec(self):
        self.assertEqual(self.room1.game._start_countdown_sec, 0)
        self.room1.game.ready_to_start(self.player1)
        self.room1.game.ready_to_start(self.player2)
        self.assertEqual(self.room1.game._start_countdown_sec, 0)
        self.room1.game.remove_player(self.player2)
        self.assertEqual(self.room1.game._start_countdown_sec, -1)

        self.assertEqual(self.room2.game._start_countdown_sec, -1)
        self.room2.join_the_game(self.player1)  # , money_in_play=1000
        self.assertEqual(self.room2.game._start_countdown_sec, -1)
        self.room2.join_the_game(self.player2)  # , money_in_play=1000
        self.assertEqual(self.room2.game._start_countdown_sec, 15)
        self.room2.game.ready_to_start(self.player1)
        self.assertEqual(self.room2.game._start_countdown_sec, 15)
        self.room2.game.ready_to_start(self.player2)
        self.assertEqual(self.room2.game._start_countdown_sec, 3)

        # waiting_for_other_players_countdown_sec < start_game_countdown_sec
        self.room2.game.ready_to_start(self.player1, False)
        self.assertEqual(self.room2.game._start_countdown_sec, 15)
        self.room2.room_model.waiting_for_other_players_countdown_sec = -1
        self.assertEqual(self.room2.game._start_countdown_sec, 3)
        self.room2.room_model.waiting_for_other_players_countdown_sec = 0
        self.assertEqual(self.room2.game._start_countdown_sec, 3)
        self.room2.room_model.waiting_for_other_players_countdown_sec = 2
        self.assertEqual(self.room2.game._start_countdown_sec, 3)

    def test_is_game_can_be_started(self):
        # Already started
        self.assertEqual(len(self.room1.game._available_player_list), 2)
        self.assertEqual(self.room1.game.game_config_model.min_players_to_start, 2)
        self.assertEqual(self.room1.game._is_in_progress, True)

        self.assertEqual(self.room1.game._is_game_can_be_started, False)

        # Game is not started
        self.room1.game._is_in_progress = False

        self.assertEqual(self.room1.game._is_game_can_be_started, True)

        # Not enough players to start
        self.room1.game.game_config_model.min_players_to_start = 3

        self.assertEqual(self.room1.game._is_game_can_be_started, False)

    def test_available_player_list(self):
        self.assertEqual(self.room1.game._available_player_list, [self.player1, self.player2])

        self.player2.money_in_play = 0
        self.assertEqual(self.room1.game._available_player_list, [self.player1])

        self.player1.money_in_play = -1
        self.assertEqual(self.room1.game._available_player_list, [])

        self.player2.money_in_play = 1
        self.assertEqual(self.room1.game._available_player_list, [self.player2])

    def test_init(self):
        super().test_init()

        self.assertIsNotNone(self.room1.game.logging)
        self.assertEqual(self.room1.game.room, self.room1)
        self.assertEqual(self.room1.game.house_config, self.house_config)
        self.assertEqual(self.room1.game.room_model, self.lobby.room_by_id["1"])
        self.assertEqual(self.room1.game.game_config_model, self.room1.room_model.game_config_model)
        self.assertIsInstance(self.room1.game._start_game_timer, AbstractTimer)
        self.assertIsInstance(self.room1.game._resume_game_timer, AbstractTimer)
        self.assertIsInstance(self.room1.game._game_timer, AbstractTimer)
        self.assertIsInstance(self.room1.game._show_game_winner_timer, AbstractTimer)
        self.assertIsInstance(self.room1.game._show_tournament_winner_timer, AbstractTimer)
        self.assertEqual(self.room1.game._rebuying_timers, [])
        self.assertEqual(self.room1.game.tournament_players, [])
        self.assertEqual(self.room1.game._is_in_progress, False)
        self.assertEqual(self.room1.game._is_paused, False)

    def test_dispose(self):
        self.room1.game._reset_game = Mock()
        self.room1.game._is_in_progress = True
        self.room1.game._is_paused = True
        self.room1.game._rebuying_timers = [Mock()]
        timers = [self.room1.game._start_game_timer, self.room1.game._resume_game_timer,
                  self.room1.game._game_timer, self.room1.game._show_game_winner_timer,
                  self.room1.game._show_tournament_winner_timer]
        for timer in timers:
            timer.start()
            self.assertEqual(timer.running, True)

        super().test_dispose()

        self.room1.game._reset_game.assert_called_once()
        self.assertIsNone(self.room1.game.room)
        self.assertIsNone(self.room1.game.house_config)
        self.assertIsNone(self.room1.game.room_model)
        self.assertIsNone(self.room1.game.game_config_model)
        self.assertIsNone(self.room1.game.logging)
        self.assertEqual(self.room1.game._is_in_progress, False)
        self.assertEqual(self.room1.game._is_paused, False)
        self.assertEqual(self.room1.game._rebuying_timers, [])
        for timer in timers:
            self.assertEqual(timer.running, False)

    # Start

    def test_on_add_player(self):
        super().test_on_add_and_remove_player()

        self.room1.game._refresh_starting_game = Mock()
        connected_player = Mock(is_connected=True)
        disconnected_player = Mock(is_connected=False)
        self.room1.game._is_in_progress = True

        self.room1.game._on_add_player(connected_player)
        self.room1.game._on_add_player(disconnected_player)
        self.room1.game._is_in_progress = False
        self.room1.game._on_add_player(disconnected_player)

        self.room1.game._refresh_starting_game.assert_not_called()

        # Refresh starting process only between games and for connected player added
        self.room1.game._on_add_player(connected_player)

        self.room1.game._refresh_starting_game.assert_called_once_with(connected_player)

    def test_on_remove_player(self):
        # super().test_on_add_and_remove_player()

        self.room1.game._refresh_starting_game = Mock()
        self.room1.game._check_end_game = Mock()
        connected_player = Mock(is_connected=True)
        disconnected_player = Mock(is_connected=False)
        self.room1.game._is_in_progress = True

        self.room1.game._on_remove_player(connected_player)
        self.room1.game._on_remove_player(disconnected_player)
        self.room1.game._is_in_progress = False
        self.room1.game._on_remove_player(connected_player)
        self.room1.game._on_remove_player(disconnected_player)

        self.assertEqual(self.room1.game._refresh_starting_game.call_count, 4)
        self.assertEqual(self.room1.game._check_end_game.call_count, 4)

    def test_ready_to_start(self):
        player = Mock()
        self.room1.game._refresh_starting_game = Mock()
        self.assertEqual(self.room1.game._ready_to_start_players, [])

        # Game started
        self.assertEqual(self.room1.game._is_in_progress, True)

        # (Set player ready)
        self.room1.game.ready_to_start(player, True)

        self.assertEqual(self.room1.game._ready_to_start_players, [])
        self.room1.game._refresh_starting_game.assert_not_called()

        # (Set player not ready)
        self.room1.game.ready_to_start(player, False)

        self.assertEqual(self.room1.game._ready_to_start_players, [])
        self.room1.game._refresh_starting_game.assert_not_called()

        # Game finished
        self.room1.game._is_in_progress = False

        # (Set player ready)
        self.room1.game.ready_to_start(player)

        self.assertEqual(self.room1.game._ready_to_start_players, [player])
        self.room1.game._refresh_starting_game.assert_called_once_with(player)
        self.room1.game._refresh_starting_game.reset_mock()

        # (Set player not ready)
        self.room1.game.ready_to_start(player, False)

        self.assertEqual(self.room1.game._ready_to_start_players, [])
        self.room1.game._refresh_starting_game.assert_called_once_with(player)

    def test_refresh_starting_game(self):
        player = Mock(place_index=3)
        self.room1._check_start_game = Mock()
        self.room1.send_ready_to_start = Mock()

        self.room1.room_model.waiting_for_other_players_countdown_sec = -1
        self.assertEqual(self.room1.game._is_in_progress, True)

        # Already started
        self.room1.game._refresh_starting_game(player)

        self.room1._check_start_game.assert_not_called()
        self.room1.send_ready_to_start.assert_not_called()

        # Not started
        # (ready_to_start disabled)
        self.room1.game._is_in_progress = False

        self.room1.game._refresh_starting_game(player)

        self.assertEqual(self.room1._check_start_game.call_count, 1)
        self.room1.send_ready_to_start.assert_not_called()

        # (ready_to_start still disabled)
        self.room1.room_model.waiting_for_other_players_countdown_sec = 0

        self.room1.game._refresh_starting_game(player)

        self.assertEqual(self.room1._check_start_game.call_count, 2)
        self.room1.send_ready_to_start.assert_not_called()

        # (ready_to_start enabled, player is not ready)
        self.room1.room_model.waiting_for_other_players_countdown_sec = 10

        self.room1.game._refresh_starting_game(player)

        self.assertEqual(self.room1._check_start_game.call_count, 3)
        self.room1.send_ready_to_start.assert_called_once_with(3, False, 10)

        # (Player is ready)
        self.room1.game.ready_to_start(player)

        self.room1.game._refresh_starting_game(player)

        self.assertEqual(self.room1._check_start_game.call_count, 3)
        self.room1.send_ready_to_start.assert_called_once_with(3, True, 10)

    def test_check_start_game(self):
        self.room1.game._start_game = Mock()

        # Started
        self.assertEqual(self.room1.game._is_in_progress, True)

        self.assertEqual(self.room1.game._check_start_game(), False)
        self.room1.game._start_game.assert_not_called()

        # Not started
        # (Start immediately)
        self.room1.game._is_in_progress = False
        self.room1.room_model.waiting_for_other_players_countdown_sec = -1
        self.room1.room_model.start_game_countdown_sec = -1

        self.assertEqual(self.room1.game._check_start_game(), True)
        self.assertEqual(self.room1.game._start_game_timer.running, False)
        self.room1.game._start_game.assert_called_once()
        self.room1.game._start_game.reset_mock()

        # (Start after delay)
        self.room1.room_model.start_game_countdown_sec = self.DELAY_SEC

        self.assertEqual(self.room1.game._check_start_game(), True)
        self.assertEqual(self.room1.game._start_game_timer.running, True)
        self.room1.game._start_game.assert_not_called()

        # (Just before start)
        time.sleep(self.DELAY_BEFORE_SEC)
        self.assertEqual(self.room1.game._start_game_timer.running, True)
        self.room1.game._start_game.assert_not_called()

        # (Restart timer)
        self.assertEqual(self.room1.game._check_start_game(), True)

        # (Just before start)
        time.sleep(self.DELAY_BEFORE_SEC)
        self.assertEqual(self.room1.game._start_game_timer.running, True)
        self.room1.game._start_game.assert_not_called()

        # (Started)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)
        self.assertEqual(self.room1.game._start_game_timer.running, False)
        self.room1.game._start_game.assert_called_once()

    def test_start_game(self):
        self.room2.game._reset_game = Mock()
        self.room2.game._on_start_game = Mock()
        self.room2.game._on_game_timeout = Mock()
        self.room2.game.room_model.min_buy_in = 500
        self.room2.game.room_model.game_timeout_sec = 0

        # Started
        self.assertEqual(self.room2.game._is_in_progress, True)

        self.room2.game._start_game()

        self.room2.game._reset_game.assert_not_called()
        self.room2.game._on_start_game.assert_not_called()

        # Not started
        self.room2.game._is_in_progress = False
        connected_player = Mock(is_connected=True, is_sit_out=False, money_in_play=1000)
        disconnected_player = Mock(is_connected=False, is_sit_out=False, money_in_play=1000)
        sit_out_player = Mock(is_connected=True, is_sit_out=True, money_in_play=1000)
        no_money_player = Mock(is_connected=True, is_sit_out=False, money_in_play=100)
        self.room2.game.player_list = [connected_player, disconnected_player,
                                       sit_out_player, no_money_player]
        for player in self.room2.game.player_list:
            player.is_playing = False

        # (Try start with only one player available)
        self.room2.game._start_game()

        self.assertFalse(self.room2.game._is_in_progress)
        self.room2.game._reset_game.assert_not_called()
        self.room2.game._on_start_game.assert_not_called()
        self.room2.game._on_game_timeout.assert_not_called()
        for player in self.room2.game.player_list:
            self.assertFalse(player.is_playing)

        # (Start OK)
        connected_player2 = Mock(is_connected=True, is_sit_out=False, money_in_play=1000)
        connected_player2.is_playing = False
        self.room2.game.player_list.append(connected_player2)

        self.room2.game._start_game()

        self.assertTrue(self.room2.game._is_in_progress)
        self.room2.game._reset_game.assert_called_once()
        self.room2.game._on_start_game.assert_called_once()
        self.room2.game._on_game_timeout.assert_not_called()
        self.assertFalse(self.room2.game._game_timer.running)
        self.assertEqual(connected_player.is_playing, True)
        self.assertEqual(connected_player2.is_playing, True)
        self.assertEqual(disconnected_player.is_playing, False)
        self.assertEqual(sit_out_player.is_playing, False)
        self.assertEqual(no_money_player.is_playing, False)

        # (Start with _game_timer)
        self.room2.game._is_in_progress = False
        self.room2.game.room_model.game_timeout_sec = self.DELAY_SEC

        self.room2.game._start_game()

        self.assertTrue(self.room2.game._is_in_progress)
        self.assertTrue(self.room2.game._game_timer.running)
        self.room2.game._on_game_timeout.assert_not_called()

        # (Just before game end)
        time.sleep(self.DELAY_BEFORE_SEC)

        self.assertTrue(self.room2.game._game_timer.running)
        self.room2.game._on_game_timeout.assert_not_called()

        # (Game end on timeout)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        self.assertFalse(self.room2.game._game_timer.running)
        self.room2.game._on_game_timeout.assert_called_once()

    def test_on_start_game(self):
        self.room1.game._on_start_game()

    def test_reset_game(self):
        self.room1.send_reset_game = Mock()
        self.player1.reset_game_state = Mock()
        self.player2.reset_game_state = Mock()
        self.room1.game.self._ready_to_start_players = [self.player1]
        for attr in dir(self.room1.game):
            if attr.endswith("timer"):
                timer = getattr(self.room1.game, attr)
                timer.start(delay_sec=self.DELAY_SEC)

        self.room1.game._reset_game()

        self.room1.send_reset_game.assert_called_once()
        self.player1.reset_game_state.assert_called_once()
        self.player2.reset_game_state.assert_called_once()
        self.assertEqual(self.room1.game.self._ready_to_start_players, [])
        for attr in dir(self.room1.game):
            if attr.endswith("timer"):
                timer = getattr(self.room1.game, attr)
                self.assertFalse(timer.running)

    def test_pause_resume_game(self):
        self.room1.game.room_model.resume_game_countdown_sec = 0
        self.room1.game._do_pause_game = Mock()
        self.room1.game._do_resume_game = Mock()
        self.room1.send_pause_game = Mock()
        self.assertFalse(self.room1.game._is_paused)

        # Not started
        self.room1.game._is_in_progress = False

        # (Pause)
        self.room1.game.pause_game()
        self.room1.game.pause_game()

        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game.is_paused)
        self.room1.game._do_pause_game.assert_not_called()
        self.room1.game._do_resume_game.assert_not_called()
        self.room1.send_pause_game.assert_not_called()

        # (Resume)
        self.room1.game.resume_game()
        self.room1.game.resume_game()

        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game.is_paused)
        self.room1.game._do_pause_game.assert_not_called()
        self.room1.game._do_resume_game.assert_not_called()
        self.room1.send_pause_game.assert_not_called()

        # Started
        self.room1.game._is_in_progress = True

        # (Pause)
        self.room1.game.pause_game()
        self.room1.game.pause_game()

        self.assertTrue(self.room1.game._is_paused)
        self.assertTrue(self.room1.game.is_paused)
        self.room1.game._do_pause_game.assert_called_once()
        self.room1.game._do_resume_game.assert_not_called()
        self.room1.send_pause_game.assert_not_called()

        # (Resume)
        self.room1.game.resume_game()
        self.room1.game.resume_game()

        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game.is_paused)
        self.room1.game._do_pause_game.assert_called_once()
        self.room1.game._do_resume_game.assert_called_once()
        self.room1.send_pause_game.assert_not_called()
        self.assertFalse(self.room2.game._resume_game_timer.running)

        # Test with resume delay
        self.room1.game._do_resume_game.reset_mock()
        self.room1.game.room_model.resume_game_countdown_sec = self.DELAY_SEC
        self.room1.game.pause_game()

        # (Start resume...)
        self.room1.game.resume_game()

        self.assertFalse(self.room1.game._is_paused)
        self.assertTrue(self.room1.game.is_paused)
        self.assertTrue(self.room1.game._is_resuming_pause)
        self.room1.game._do_resume_game.assert_not_called()
        self.room1.send_pause_game.assert_called_once_with(False, self.DELAY_SEC)
        self.assertTrue(self.room2.game._resume_game_timer.running)

        # (Just before resumed)
        time.sleep(self.DELAY_BEFORE_SEC)

        self.assertTrue(self.room1.game.is_paused)
        self.room1.game._do_resume_game.assert_not_called()
        self.assertTrue(self.room2.game._resume_game_timer.running)
        self.room2.game._on_game_timeout.assert_not_called()

        # (Resumed)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        self.assertFalse(self.room1.game._is_paused)
        self.assertFalse(self.room1.game.is_paused)
        self.assertFalse(self.room1.game._is_resuming_pause)
        self.room1.game._do_resume_game.assert_called_once()
        self.assertFalse(self.room2.game._resume_game_timer.running)

    def test_do_pause_and_resume_game(self):
        self.room1.send_pause_game = Mock()
        self.room1._on_resume_game = Mock()

        for attr in dir(self.room1.game):
            if attr.endswith("timer"):
                timer = getattr(self.room1.game, attr)
                if isinstance(timer, AbstractTimer):
                    timer.start(delay_sec=self.DELAY_SEC)
                    self.assertFalse(timer.paused)

        # Do pause
        self.room1.game._do_pause_game()

        self.room1.send_pause_game.assert_called_once_with(True)
        for attr in dir(self.room1.game):
            if attr.endswith("timer"):
                timer = getattr(self.room1.game, attr)
                self.assertTrue(timer.paused)

        # Do resume
        self.room1.game._do_resume_game()

        self.room1.send_pause_game.assert_called_with(False)
        for attr in dir(self.room1.game):
            if attr.endswith("timer"):
                timer = getattr(self.room1.game, attr)
                self.assertFalse(timer.paused)
        self.room1._on_resume_game.assert_called_once()

    def test_on_resume_game(self):
        self.room1._on_start_game = Mock()

        self.room1.game._on_resume_game()

        self.room1._on_start_game.assert_called_once()

    def test_check_end_game(self):
        self.room1.game._end_game = Mock()
        self.assertEqual(self.room1.game.player_list, [self.player1, self.player2])
        self.assertEqual(self.room1.game._is_in_progress, True)

        # Not finished
        result = self.room1._check_end_game()

        self.assertFalse(result)
        self.room1.game._end_game.assert_not_called()

        # Already finished
        self.room1.game._is_in_progress = False
        result = self.room1._check_end_game()

        self.assertTrue(result)
        self.room1.game._end_game.assert_not_called()

        # Finished
        self.room1.game._is_in_progress = True
        self.player1.is_playing = False
        result = self.room1._check_end_game()

        self.assertTrue(result)
        self.room1.game._end_game.assert_called_once()

    def test_on_game_timeout(self):
        self.room1._end_game = Mock()

        self.room1.game._on_game_timeout()

        self.room1._end_game.assert_called_once()

    def test_end_game(self):
        self.room1.room_model.show_game_winner_delay_sec = 0
        self.room1.game._on_end_game = Mock()
        self.room1.game._is_in_progress = False

        # Already finished
        self.room1.game._is_in_progress = False
        self.room1._end_game()

        self.room1.game._on_end_game.assert_not_called()

        # Not finished
        self.room1.game._is_in_progress = True
        self.room1._end_game()

        self.assertFalse(self.room1.game._is_in_progress)
        self.room1.game._on_end_game.assert_called_once()

        # _on_end_game called through _find_game_winners
        self.room1.game._find_game_winners = Mock()
        self.room1.game._is_in_progress = True
        self.room1._end_game()

        self.room1.game._find_game_winners.assert_called_once()

    def test_find_game_winners(self):
        # show_game_winner_delay_sec = 0
        self.room1.room_model.show_game_winner_delay_sec = 0
        callback = Mock()

        self.room1.game._find_game_winners(callback)

        callback.assert_called_once()
        callback.reset_mock()

        # show_game_winner_delay_sec = -1
        self.room1.room_model.show_game_winner_delay_sec = -1

        self.room1.game._find_game_winners(callback)

        callback.assert_called_once()
        callback.reset_mock()

        # Not empty show_game_winner_delay_sec
        self.room1.room_model.show_game_winner_delay_sec = self.DELAY_SEC

        self.room1.game._find_game_winners(callback)

        callback.assert_not_called()

        time.sleep(self.DELAY_BEFORE_SEC)
        # (Just before delay ends)
        callback.assert_not_called()

        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)
        # (After delay ends)
        callback.assert_called_once()

    def test_on_end_game(self):
        self.assertTrue(self.room1.game.game_config_model.is_reset_on_game_finish)
        self.room1.game._player_no_money_in_play = Mock()
        self.room1.game._start_game = Mock()
        self.room1.game._reset_game = Mock()

        # Start on end
        self.room1.game._on_end_game()

        self.room1.game._player_no_money_in_play.assert_not_called()
        self.room1.game._start_game.assert_called_once()
        self.room1.game._reset_game.assert_not_called()
        self.room1.game._start_game.reset_mock()

        # No money for one of two players, can't start game - reset
        self.player1.money_in_play = 0
        self.room1.game.game_config_model.is_reset_on_game_finish = True

        self.room1.game._on_end_game()

        self.room1.game._player_no_money_in_play.assert_called_once_with(self.player1)
        self.room1.game._start_game.assert_not_called()
        self.room1.game._reset_game.assert_called_once()
        self.room1.game._player_no_money_in_play.reset_mock()
        self.room1.game._reset_game.reset_mock()

        # Can't start game - reset on game end disabled
        self.room1.game.game_config_model.is_reset_on_game_finish = False

        self.room1.game._on_end_game()

        self.room1.game._player_no_money_in_play.assert_called_once_with(self.player1)
        self.room1.game._start_game.assert_not_called()
        self.room1.game._reset_game.assert_not_called()

    # Send

    def test_send_player_wins(self):
        self.room1.send_player_wins_the_tournament = Mock()
        self.room1.send_player_wins = Mock()
        self.player2.money_in_play = 5200

        self.room1.game.send_player_wins(self.player2, 1500)

        self.room1.send_player_wins_the_tournament.assert_not_called()
        self.room1.send_player_wins.assert_called_once_with(3, 1500, 5200)

        self.room1.game.send_player_wins(self.player2, 1700, True)

        self.room1.send_player_wins_the_tournament.assert_called_once_with(3, 1700, 5200)
        self.room1.send_player_wins.assert_called_once_with(3, 1500, 5200)

        # (Not changed)
        self.assertEqual(self.player2.money_in_play, 5200)

    def test_player_no_money_in_play(self):
        self.room1.room_model.hold_place_while_rebuying_for_sec = self.DELAY_SEC
        self.player1.protocol = Mock()
        self.player2.protocol = Mock()
        self.player3.protocol = Mock()

        self.assertEqual(len(self.room1.game._rebuying_timers), 0)
        self.player1.money_in_play = 0  # to be removed
        self.player2.money_in_play = 0  # to be rebought
        self.player3.money_in_play = 0  # not in the game
        self.player3.money_in_play = 1  # not in the game, with money

        # Show cash box dialog on no money
        self.room1.game._player_no_money_in_play(self.player1)
        self.room1.game._player_no_money_in_play(self.player1)
        self.room1.game._player_no_money_in_play(self.player2)
        self.room1.game._player_no_money_in_play(self.player3)

        self.assertEqual(self.player1.protocol.show_cashbox_dialog.call_count, 2)
        self.player1.protocol.show_cashbox_dialog.assert_called()
        self.player2.protocol.show_cashbox_dialog.assert_called_once()
        self.player3.protocol.show_cashbox_dialog.assert_called_once()
        self.assertEqual(len(self.room1.game._rebuying_timers), 4)
        self.assertIn(self.room1.game.player_list, self.player1)
        self.assertIn(self.room1.game.player_list, self.player2)
        self.assertNotIn(self.room1.game.player_list, self.player2)

        # (Before timeout)
        time.sleep(self.DELAY_BEFORE_SEC)

        self.assertEqual(len(self.room1.game._rebuying_timers), 4)
        self.assertIn(self.room1.game.player_list, self.player1)
        self.assertIn(self.room1.game.player_list, self.player2)

        # Rebuy
        self.player2.money_in_play = 1

        # (After timeout)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        self.assertEqual(len(self.room1.game._rebuying_timers), 0)
        self.assertNotIn(self.room1.game.player_list, self.player1)
        self.assertIn(self.room1.game.player_list, self.player2)

    def test_get_player_info(self):
        self.player1.protocol = Mock()

        # Wrong place_index
        self.room1.game.get_player_info(self.player1, -1)
        self.room1.game.get_player_info(self.player1, 9)

        self.player1.protocol.player_info.assert_not_called()

        # With no player
        self.room1.game.get_player_info(self.player1, 1)

        self.player1.protocol.player_info.assert_called_with(1, None)

        # Self info
        self.room1.game.get_player_info(self.player1, 0)

        self.player1.protocol.player_info.assert_called_with(0, self.player1.export_public_data())

        # Another player info
        self.room1.game.get_player_info(self.player1, 3)

        self.player1.protocol.player_info.assert_called_with(3, self.player2.export_public_data())

    def test_get_all_player_info(self):
        self.player1.protocol = Mock()

        self.room1.game.get_all_player_info(self.player1)

        self.assertEqual(self.player1.protocol.player_info.call_args_list, [
            call(0, self.player1.export_public_data()),
            call(1, None), call(2, None),
            call(3, self.player2.export_public_data()),
            call(4, None), call(5, None), call(6, None), call(7, None), call(8, None)
        ])

    def test_action1(self):
        # (No exception)
        self.room1.game.action1([])

    def test_action2(self):
        # (No exception)
        self.room1.game.action2([])

    def test_process_raw_binary_action(self):
        # (No exception)
        self.room1.game.process_raw_binary_action()

    def test_create_timer(self):
        callback = Mock()
        timer = self.room1.game.create_timer(callback, 14, "name")

        self.assertIsInstance(timer, AbstractTimer)
        self.assertEqual(timer.callback, callback)
        self.assertEqual(timer.delay_sec, 14)
        self.assertEqual(timer.repeat_count, 1)
        self.assertEqual(timer.name, "name")
