import time
from unittest import TestCase
from unittest.mock import Mock

from napalm.async import AbstractTimer
from napalm.play.core import HouseConfig
from napalm.play.game import Game, GameConfigModel
from napalm.play.house import House
from napalm.play.test import utils
from napalm.test.test_async import BaseTestTimer


class TestGameWorkflow(TestCase):

    game_class = Game
    game_config_model_class = GameConfigModel
    room_class = None
    player_class = None
    data_dir_path = "game_configs/"

    RESOLUTION_SEC = BaseTestTimer.RESOLUTION_SEC
    DELAY_SEC = BaseTestTimer.DELAY_SEC
    DELAY_BEFORE_SEC = BaseTestTimer.delay_before()
    DELAY_AFTER_SEC = BaseTestTimer.delay_after()
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
        super().setUp()

        AbstractTimer.resolution_sec = BaseTestTimer.RESOLUTION_SEC

        self.house_config = HouseConfig(house_id="1",
                                        data_dir_path=self.data_dir_path,
                                        game_class=self.game_class,
                                        game_config_model_class=self.game_config_model_class,
                                        room_class=self.room_class,
                                        player_class=self.player_class)
        # (To make some tests faster)
        self.house_config.house_model.is_save_house_state_on_any_change = False
        self.house_config.game_class = self.game_class
        self.house = House(self.house_config)
        self.lobby = self.house._lobby_by_id["1"]
        self.room1 = self.lobby.room_by_id["1"]
        self.room2 = self.lobby.room_by_id["2"]
        self.room3 = self.lobby.room_by_id["3"]
        for room_model in [self.room1.room_model, self.room2.room_model, self.room3.room_model]:
            room_model.resume_game_countdown_sec = self.DELAY_SEC
            room_model.rebuying_sec = self.DELAY_SEC / 2
            room_model.apply_round_delay_sec = self.DELAY_SEC
            room_model.round_timeout_sec = -1
            room_model.between_rounds_delay_sec = self.DELAY_SEC * 1.5
            room_model.turn_timeout_sec = self.DELAY_SEC
            room_model.game_timeout_sec = -1
            room_model.show_game_winner_delay_sec = self.DELAY_SEC
            room_model.show_tournament_winner_max_delay_sec = self.DELAY_SEC * 2

        self.user1 = utils.create_user(self.house_config, "123", 20000)
        self.player1 = utils.create_player(self.user1, lobby=self.lobby)  # Connected
        self.user2 = utils.create_user(self.house_config, "456", 20000)
        self.player2 = utils.create_player(self.user2, False, self.lobby)  # Not connected
        self.user3 = utils.create_user(self.house_config, "789", 20000)
        self.player3 = utils.create_player(self.user3, True, self.lobby)  # Connected
        self.user4 = utils.create_user(self.house_config, "246", 20000)
        self.player4 = utils.create_player(self.user4, True, self.lobby)  # Connected
        self.player5 = utils.create_player(self.user4, True, self.lobby)  # Connected

        self.room1.add_player(self.player1)
        self.room1.add_player(self.player2)
        self.room1.add_player(self.player3)
        self.room1.join_the_game(self.player1, money_in_play=1000)  # , money_in_play=1000
        self.room1.join_the_game(self.player2, 3, money_in_play=1000)  # , money_in_play=1000
        self.lobby.join_the_room(self.player4, 1)  # , money_in_play=1000
        # (Join the rooms to create "game" instance in room)
        self.room1.add_player(Mock(place_index=-1))
        self.room2.add_player(Mock(place_index=-1))
        self.room3.add_player(Mock(place_index=-1))

        self.assertFalse(self.room1.game._is_in_progress)  # False: only 1 player connected
        self.assertIsInstance(self.room1.game, self.game_class)
        self.assertIsInstance(self.room1.game.game_config_model, self.game_config_model_class)

    def tearDown(self):
        # TestGamePlayerManagerMixIn.tearDown(self)
        self.house_config.dispose()

    def test_game_workflow(self):
        # No players
        self.room1.game._remove_all_players()
        self.assertFalse(self.room1.game._is_in_progress)

        self.room1.room_model.rebuying_sec = self.DELAY_SEC / 2
        # (Sending mocks)
        self.room1.send_ready_to_start = Mock()
        self.room1.send_reset_game = Mock()
        self.room1.send_pause_game = Mock()
        self.player1.reset_game_state = Mock()
        self.player2.reset_game_state = Mock()
        self.player3.reset_game_state = Mock()

        # Join one player
        self.room1.join_the_game(self.player1, 1, 1000)

        self.assertFalse(self.room1.game._is_in_progress)
        self.room1.send_reset_game.assert_not_called()

        # Start game after 2 connected players joined
        self.assertEqual(self.player1.is_playing, False)
        self.assertEqual(self.player2.is_playing, False)
        self.player2.protocol = Mock(is_ready=True)  # make player connected

        self.room1.join_the_game(self.player2, 1, 1000)

        self.assertTrue(self.room1.game._is_in_progress)
        self.assertEqual(self.room1.game.player_list, [self.player1, self.player2])
        self.assertEqual(self.room1.game._game_timer.running, False)  # game_time_sec==-1
        self.assertEqual(self.player2.place_index, 2)
        self.assertEqual(self.player1.is_playing, True)
        self.assertEqual(self.player2.is_playing, True)
        self.room1.send_reset_game.assert_called_once()
        self.room1.send_reset_game.reset_mock()
        self.player1.reset_game_state.assert_called_once()
        self.player2.reset_game_state.assert_called_once()
        self.player1.reset_game_state.reset_mock()
        self.player2.reset_game_state.reset_mock()

        # Join 3rd during game
        self.room1.join_the_game(self.player3, money_in_play=5000)

        self.assertEqual(self.player3.is_playing, False)
        self.assertEqual(self.player3.place_index, 0)
        self.assertEqual(self.room1.game.player_list, [self.player3, self.player1, self.player2])
        # (After all joined)
        self.room1.send_ready_to_start.assert_not_called()  # waiting_for_other_players_countdown_sec==0
        self.player2.reset_game_state.assert_not_called()

        # Pause
        self.assertEqual(self.room1.game._is_paused, False)

        self.room1.game.pause_game()

        self.assertEqual(self.room1.game._is_paused, True)
        self.room1.send_pause_game.assert_called_once_with(True)
        # (Other asserts could be added)

        # Resume
        self.room1.game.resume_game()

        self.assertEqual(self.room1.game._is_paused, False)
        self.room1.send_pause_game.assert_called_with(False, self.DELAY_SEC)
        # (Other asserts could be added)

        # Check end (no end if only no money)
        self.room1.game._on_end_game = Mock(side_effect=self.room1.game._on_end_game)
        self.assertFalse(self.room1.game._check_end_game())
        self.assertTrue(self.room1.game._is_in_progress)
        self.assertFalse(self.room1.game._check_end_game())

        self.assertTrue(self.room1.game._is_in_progress)
        self.room1.game._on_end_game.assert_not_called()
        self.player2.protocol.show_cashbox_dialog.assert_not_called()

        # Check end (OK if not playing)
        self.player2.money_in_play = 0
        self.player2.is_playing = False
        self.assertEqual(self.room1.room_model.show_game_winner_delay_sec, self.DELAY_SEC)

        # (Only player1 left playing; player3 is waiting for new game)
        self.assertTrue(self.room1.game._check_end_game())

        self.assertFalse(self.room1.game._is_in_progress)
        self.room1.game._on_end_game.assert_not_called()
        self.player2.protocol.show_cashbox_dialog.assert_not_called()

        # Waiting for winner showing end
        time.sleep(self.DELAY_BEFORE_SEC)

        self.assertFalse(self.room1.game._is_in_progress)
        self.room1.game._on_end_game.assert_not_called()
        self.assertIn(self.player2, self.room1.game.player_list)
        self.player2.protocol.show_cashbox_dialog.assert_not_called()

        # Didn't buy in within rebuying_sec interval
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)
        # time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)  # needed for the code in another thread to be executed

        self.assertIn(self.player2, self.room1.game.player_list)
        self.room1.game._on_end_game.assert_called_once()
        self.player2.protocol.show_cashbox_dialog.assert_called_once()
        # (New game started)
        self.assertTrue(self.room1.game._is_in_progress)
        self.assertEqual(self.player1.is_playing, True)
        self.assertEqual(self.player2.is_playing, False)
        self.assertEqual(self.player3.is_playing, True)
        self.player1.reset_game_state.assert_called_once()
        self.player2.reset_game_state.assert_called_once()
        self.player3.reset_game_state.assert_called_once()
        self.room1.send_reset_game.assert_called_once()

        # Holding seat during rebuying
        time.sleep(self.DELAY_BEFORE_SEC / 2)

        # (Commented because timing is not precise)
        # self.assertIn(self.player2, self.room1.game.player_list)

        # Didn't buy within rebuying_sec interval
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC / 2)

        self.assertNotIn(self.player2, self.room1.game.player_list)

        # # Wait for the moment just before new game starts...
        # time.sleep(self.DELAY_BEFORE_SEC * 1.5)
        #
        # # (Just before new game)
        # self.assertFalse(self.room1.game._is_in_progress)
        # self.room1.send_reset_game.assert_not_called()
        #
        # # (Wait a little more...)
        # time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        # Remove player - end game
        self.room1.leave_the_game(self.player3)

        self.assertFalse(self.room1.game._is_in_progress)
        self.assertEqual(self.room1.game._player_by_place_index, {1: self.player1})
        self.assertEqual(self.player1.is_playing, True)
        self.assertEqual(self.player2.is_playing, False)
        self.assertEqual(self.player3.is_playing, False)

    def test_monopoly_like_game_workflow(self):
        """Test timers, ready to start, join between games only,
        add time to timer.delay and reduce timer.elapsed time during timer running.
        Note: all scalar multipliers (like "* 2") near time variables are for
        passing tests successfully. """

        # (Make delays shorter than in json configs)
        self.room2.room_model.waiting_for_other_players_countdown_sec = self.DELAY_SEC * 2
        self.room2.room_model.start_game_countdown_sec = self.DELAY_SEC
        self.room2.room_model.resume_game_countdown_sec = self.DELAY_SEC
        self.room2.room_model.game_timeout_sec = self.DELAY_SEC * 2
        self.room2.room_model.show_game_winner_delay_sec = self.DELAY_SEC * 1.5
        self.room2.room_model.apply_round_delay_sec = 0
        self.room2.game.game_config_model.is_join_only_between_games = True
        # (Clear the game) (already clear)
        # self.room2.game._remove_all_players()
        # (Sending mocks)
        self.room2.send_ready_to_start = Mock()
        self.room2.send_reset_game = Mock()
        self.room2.send_pause_game = Mock()
        self.room2.game._on_start_game = Mock()

        # Empty game
        self.assertFalse(self.room2.game._is_in_progress)

        # Join the 1st
        self.room2.add_player(self.player1)
        self.room2.join_the_game(self.player1, 1, 1000)

        self.assertTrue(self.player1.is_connected)
        self.assertFalse(self.room2.game._is_in_progress)
        self.room2.send_ready_to_start.assert_called_once_with(1, False, -1)
        self.room2.send_ready_to_start.reset_mock()

        # Try to join the 2nd (is_find_free_place_if_specified_one_taken==False)
        self.room2.game.game_config_model.is_find_free_place_if_specified_one_taken = False
        self.assertTrue(self.player3.is_connected)

        self.room2.add_player(self.player3)
        self.room2.join_the_game(self.player3, 1, 1000)

        self.assertFalse(self.room2.game._is_in_progress)
        self.assertIsNone(self.player3.game)

        # Join the 2nd
        self.room2.join_the_game(self.player3, 2, 1000)

        self.assertFalse(self.room2.game._is_in_progress)
        self.assertIsNotNone(self.player3.game)
        self.room2.send_ready_to_start.assert_called_once_with(2, False, self.DELAY_SEC * 2)
        self.room2.send_ready_to_start.reset_mock()

        # Wait for the moment just before game starts...
        time.sleep(self.DELAY_BEFORE_SEC * 2)
        # (Still not started)
        self.assertFalse(self.room2.game._is_in_progress)
        self.assertEqual(self.player1.is_playing, False)
        self.assertEqual(self.player2.is_playing, False)
        self.assertEqual(self.player3.is_playing, False)
        self.room2.send_reset_game.assert_not_called()
        self.room2.game._on_start_game.assert_not_called()

        # (Wait a little bit more...)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC * 2)

        # Game started
        self.assertTrue(self.room2.game._is_in_progress)
        self.assertEqual(self.player1.is_playing, True)
        self.assertEqual(self.player2.is_playing, False)
        self.assertEqual(self.player3.is_playing, True)
        self.room2.send_reset_game.assert_called_once()
        self.room2.send_reset_game.reset_mock()
        self.room2.game._on_start_game.assert_called_once()
        self.room2.game._on_start_game.reset_mock()

        # Try to join the 3rd
        # (is_join_only_between_games==True)
        self.assertTrue(self.room2.game.game_config_model.is_join_only_between_games)
        self.assertTrue(self.room2.game._is_in_progress)

        self.room2.add_player(self.player2)
        self.room2.join_the_game(self.player2, 5, 5000)

        self.room2.send_ready_to_start.assert_not_called()
        self.assertEqual(self.room2.game.player_list, [self.player1, self.player3])
        self.assertEqual(self.player2.game, None)
        self.assertEqual(self.player2.is_playing, False)

        # Wasting game time...
        time.sleep(max(0, self.DELAY_SEC - self.room2.game._game_timer.elapsed_time))
        self.assertFalse(self.room2.game.is_paused)
        self.assertTrue(self.room2.game._is_in_progress)

        # Pause
        self.room2.game.pause_game()
        self.room2.game.pause_game()

        # Wasting time on pause...
        self.room2.send_pause_game.assert_called_once_with(True)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC)
        # self.assertEqualRound(self.room2.game.game_elapsed_time, self.DELAY_SEC * 1.5)
        game_elapsed_time = self.room2.game.game_elapsed_time
        time.sleep(self.DELAY_SEC)
        self.assertEqual(self.room2.game.game_elapsed_time, game_elapsed_time)
        self.assertEqual(self.room2.game._is_paused, True)
        self.assertEqual(self.room2.game.is_paused, True)

        # Resume
        self.room2.game.resume_game()
        self.room2.game.resume_game()

        self.room2.send_pause_game.assert_called_with(False, self.DELAY_SEC)
        self.assertEqual(self.room2.game._is_paused, False)
        self.assertEqual(self.room2.game._is_resuming_pause, True)
        self.assertEqual(self.room2.game.is_paused, True)

        # Wait for the moment just before pause really resumed...
        time.sleep(self.DELAY_BEFORE_SEC)
        self.assertEqual(self.room2.game.is_paused, True)
        self.assertEqual(self.room2.game._game_timer.paused, True)
        self.room2.game._on_start_game.assert_not_called()

        # Resumed, game timer started again...
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)
        self.room2.send_pause_game.assert_called_with(False)
        self.assertEqual(self.room2.game.is_paused, False)
        self.assertEqual(self.room2.game._game_timer.paused, False)
        self.room2.game._on_start_game.assert_called_once()

        # Wait for the moment just before game ends...
        # time.sleep(max(0, self.DELAY_SEC - self.room2.game.game_elapsed_time - self.BETWEEN_BEFORE_AND_AFTER_SEC))
        time.sleep(self.DELAY_SEC - self.BETWEEN_BEFORE_AND_AFTER_SEC)
        self.assertTrue(self.room2.game._is_in_progress)
        # self.assertEqualRound(self.room2.game.game_elapsed_time, self.DELAY_SEC + self.DELAY_BEFORE_SEC)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC + self.DELAY_BEFORE_SEC)

        # Rewind some time
        # self.room2.game.game_elapsed_time -= self.DELAY_SEC * 1.5
        self.room2.game.game_elapsed_time = self.DELAY_BEFORE_SEC

        # Wait again for the moment just before game ends...
        time.sleep(self.DELAY_SEC)

        self.assertTrue(self.room2.game._is_in_progress)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC + self.DELAY_BEFORE_SEC)
        # self.assertEqualRound(self.room2.game.game_elapsed_time, self.DELAY_SEC + self.DELAY_BEFORE_SEC)

        # (Wait a little bit more...)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        # Game finished by game_timer
        self.assertFalse(self.room2.game._game_timer.running)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC * 2)
        self.assertFalse(self.room2.game._is_in_progress)
        show_game_winner_timer = self.room2.game.show_winner_processor.show_game_winner_timer \
            if hasattr(self.room2.game, "show_winner_processor") \
            else self.room2.game._show_game_winner_timer
        self.assertEqual(show_game_winner_timer.running, True)

        # Wait for show_game_winner_delay_sec
        time.sleep(max(0, self.DELAY_BEFORE_SEC * 1.5 - show_game_winner_timer.elapsed_time))

        self.assertFalse(self.room2.game._is_in_progress)
        self.assertEqual(show_game_winner_timer.running, True)
        self.assertEqual(self.room2.game._start_game_timer.running, False)

        # Check start new game
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC * 1.5)

        self.assertFalse(self.room2.game._is_in_progress)
        self.assertEqual(show_game_winner_timer.running, False)
        self.assertEqual(self.room2.game._start_game_timer.running, True)
        self.room2.send_ready_to_start.assert_not_called()

        # Join the 3rd
        self.player2.protocol = Mock(is_ready=False)
        self.room2.join_the_game(self.player2, 5, 5000)

        self.assertFalse(self.room2.game._is_in_progress)
        self.assertEqual(self.room2.game.player_list, [self.player1, self.player3, self.player2])
        self.assertEqual(self.player1.is_playing, True)  # Note: players marked as playing in between games interval
        self.assertEqual(self.player2.is_playing, False)
        self.assertEqual(self.player3.is_playing, True)
        # self.room2.send_ready_to_start.assert_called_once_with(5, False, self.DELAY_SEC * 2)
        self.assertFalse(self.player2.is_connected)
        self.room2.send_ready_to_start.assert_not_called()  # not connected

        # Ready to start
        self.room2.game.ready_to_start(self.player1, True)
        self.room2.send_ready_to_start.assert_called_with(1, True, self.DELAY_SEC * 2)
        self.room2.game.ready_to_start(self.player3, True)
        self.room2.send_ready_to_start.assert_called_with(2, True, self.DELAY_SEC * 2)
        self.room2.game.ready_to_start(self.player2, True)
        self.room2.send_ready_to_start.assert_called_with(5, True, self.DELAY_SEC)
        self.room2.game.ready_to_start(self.player2, False)
        self.room2.send_ready_to_start.assert_called_with(5, False, self.DELAY_SEC * 2)
        self.room2.game.ready_to_start(self.player2, True)
        self.room2.send_ready_to_start.assert_called_with(5, True, self.DELAY_SEC)

        # Wait the moment just before new game started
        time.sleep(self.DELAY_BEFORE_SEC)

        self.assertFalse(self.room2.game._is_in_progress)

        # (Wait a little bit more...)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        # Game started again
        self.assertTrue(self.room2.game._is_in_progress)
        self.assertEqual(self.player1.is_playing, True)
        self.assertEqual(self.player2.is_playing, False)  # not connected
        self.assertEqual(self.player3.is_playing, True)

        # Wasting game time...
        self.room2.game._game_timer.elapsed_time = 0  # For sure
        time.sleep(self.DELAY_SEC)

        # Add some time
        self.room2.game._game_timer.delay_sec += self.DELAY_SEC

        # Wait again for the moment just before game ends...
        time.sleep(self.DELAY_SEC + self.DELAY_BEFORE_SEC)

        self.assertTrue(self.room2.game._is_in_progress)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC * 2 + self.DELAY_BEFORE_SEC)

        # (Wait a little bit more...)
        time.sleep(self.BETWEEN_BEFORE_AND_AFTER_SEC)

        # Game finished by game_timer
        self.assertFalse(self.room2.game._is_in_progress)
        self.assertGreaterEqual(self.room2.game.game_elapsed_time, self.DELAY_SEC * 3)
