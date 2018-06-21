from unittest import TestCase
from unittest.mock import MagicMock, call, Mock

from napalm.play.core import HouseConfig
from napalm.play.game import Game
from napalm.play.house import Player, User, HouseModel
from napalm.play.lobby import Lobby, RoomModel, Room
from napalm.play.protocol import MessageType, MessageCode
from napalm.play.test import utils


class TestRoomModel(TestCase):
    room_model = None

    def setUp(self):
        super().setUp()
        house_config = HouseConfig(data_dir_path="game_configs/")
        self.room_model = RoomModel(["1", "2_room11", "1_H_10_0", [50, 100, 5000, 100000],
                                     0, -1, 6, 7, "xxx", "123", 2.5])

    def test_properties(self):
        # Imported properties
        self.assertEqual(self.room_model.room_id, "1")
        self.assertEqual(self.room_model.room_name, "2_room11")
        self.assertEqual(self.room_model.room_code, "1_H_10_0")
        self.assertEqual(self.room_model.min_stake, 50)
        self.assertEqual(self.room_model.max_stake, 100)
        self.assertEqual(self.room_model.min_buy_in, 5000)
        self.assertEqual(self.room_model.max_buy_in, 100000)
        self.assertEqual(self.room_model.max_player_count, 6)
        self.assertEqual(self.room_model.max_visitor_count, 7)
        self.assertEqual(self.room_model.room_password, "xxx")
        self.assertEqual(self.room_model.owner_user_id, "123")
        self.assertEqual(self.room_model.waiting_for_other_players_countdown_sec, 2.5)

        # is_password_needed
        self.assertEqual(self.room_model.is_password_needed, True)

        self.room_model.room_password = ""

        self.assertEqual(self.room_model.is_password_needed, False)

        # visitor_count
        self.assertEqual(self.room_model.total_player_count, 0)
        self.assertEqual(self.room_model.playing_count, 0)
        self.assertEqual(self.room_model.visitor_count, 0)

        self.room_model.total_player_count = 5
        self.room_model.playing_count = 2

        self.assertEqual(self.room_model.visitor_count, 3)

        # export_public_data
        public_data = self.room_model.export_public_data()

        expected_data = ["1", "2_room11", "1_H_10_0", [50, 100, 5000, 100000],
                         0, -1, 6, 7, False, 2, 3,
                         10, .5]
        self.assertEqual(public_data, expected_data)

    def test_room_code(self):
        self.assertEqual(self.room_model.game_id, 1)
        self.assertEqual(self.room_model.game_variation, "H")
        self.assertEqual(self.room_model.game_type, 10)
        self.assertEqual(self.room_model.room_type, 0)
        self.assertEqual(self.room_model.game_config_ids, ["1", "H", "10"])

    def test_room_type(self):
        self.assertEqual(self.room_model.room_type, 0)

        self.assertEqual(self.room_model.is_public, True)
        self.assertEqual(self.room_model.is_vip, False)
        self.assertEqual(self.room_model.is_private, False)

        self.room_model.room_type = 1

        self.assertEqual(self.room_model.is_public, False)
        self.assertEqual(self.room_model.is_vip, True)
        self.assertEqual(self.room_model.is_private, False)

        self.room_model.room_type = 2

        self.assertEqual(self.room_model.is_public, False)
        self.assertEqual(self.room_model.is_vip, False)
        self.assertEqual(self.room_model.is_private, True)

    def test_game_params(self):
        self.assertEqual(self.room_model.min_stake, 50)
        self.assertEqual(self.room_model.max_stake, 100)
        self.assertEqual(self.room_model.min_buy_in, 5000)
        self.assertEqual(self.room_model.max_buy_in, 100000)

        # Setter
        self.room_model.game_params = [150, 1200, 54000, 5100000]

        self.assertEqual(self.room_model.min_stake, 150)
        self.assertEqual(self.room_model.max_stake, 1200)
        self.assertEqual(self.room_model.min_buy_in, 54000)
        self.assertEqual(self.room_model.max_buy_in, 5100000)

        # Getter
        self.room_model.min_stake = 300
        self.room_model.max_stake = 4000
        self.room_model.min_buy_in = 60000
        self.room_model.max_buy_in = 700000

        self.assertEqual(self.room_model.game_params, [300, 4000, 60000, 700000])

    def test_constructor(self):
        room_model = RoomModel()

        self.assertFalse(room_model.room_id)
        self.assertFalse(room_model.room_name)
        self.assertFalse(room_model.room_code)
        self.assertEqual(room_model.game_params, [0, 0, 0, 0])
        self.assertEqual(room_model.max_player_count, -1)
        self.assertEqual(room_model.max_visitor_count, -1)
        self.assertFalse(room_model.room_password)
        self.assertFalse(room_model.owner_user_id)
        # Room code
        self.assertFalse(room_model.game_id)
        self.assertFalse(room_model.game_variation)
        self.assertFalse(room_model.game_type)
        self.assertFalse(room_model.room_type)
        # Game params
        self.assertFalse(room_model.min_stake)
        self.assertFalse(room_model.max_stake)
        self.assertFalse(room_model.min_buy_in)
        self.assertFalse(room_model.max_buy_in)
        # Timing
        self.assertFalse(room_model.start_game_countdown_sec)
        self.assertTrue(room_model.resume_game_countdown_sec)
        self.assertTrue(room_model.rebuying_sec)
        self.assertTrue(room_model.apply_round_delay_sec)
        self.assertTrue(room_model.round_timeout_sec)
        self.assertTrue(room_model.between_rounds_delay_sec)
        self.assertTrue(room_model.turn_timeout_sec)
        self.assertTrue(room_model.game_timeout_sec)
        self.assertTrue(room_model.show_game_winner_delay_sec)
        self.assertTrue(room_model.show_tournament_winner_max_delay_sec)
        self.assertFalse(room_model.is_reset_round_timer_on_restore)
        self.assertTrue(room_model.is_reset_turn_timer_on_restore)
        # State
        self.assertFalse(room_model.total_player_count)
        self.assertFalse(room_model.playing_count)

    def test_game_config_model(self):
        self.assertIsNotNone(self.room_model.game_config_model)
        # (Not existing "0" game_config_model id omitted)
        self.assertEqual(self.room_model.game_config_model.ids, ["1", "H", "10"])

    def test_dispose(self):
        game_config_model = self.room_model.game_config_model
        self.assertEqual(game_config_model.ids, ["1", "H", "10"])

        self.room_model.dispose()

        self.assertEqual(game_config_model.ids, None)
        self.assertIsNone(self.room_model.game_config_model)

        # With mock
        self.room_model.game_config_model = game_config_model = MagicMock()

        self.room_model.dispose()

        game_config_model.dispose.assert_called_once()
        self.assertIsNone(self.room_model.game_config_model)

    def test_on_reload(self):
        game_config_model = self.room_model.game_config_model
        self.assertEqual(self.room_model.room_id, "1")
        self.assertEqual(self.room_model.room_name, "2_room11")
        self.assertEqual(self.room_model.game_config_model.ids, ["1", "H", "10"])
        self.assertEqual(self.room_model.game_params, [50, 100, 5000, 100000])

        # Another room_code
        self.room_model.on_reload([2, "2_room11_changed", "1_OH_40_0"])

        self.assertEqual(self.room_model.room_name, "2_room11")
        self.room_model.apply_changes()
        self.assertEqual(self.room_model.room_name, "2_room11_changed")
        self.room_model.reset()
        self.assertEqual(self.room_model.room_name, "2_room11_changed")

        self.assertEqual(self.room_model.room_id, "1")
        self.assertEqual(self.room_model.room_code, "1_OH_40_0")
        self.assertEqual(self.room_model.game_config_model, game_config_model)
        self.assertEqual(self.room_model.game_config_model.ids, ["1", "OH", "40"])
        self.assertEqual(self.room_model.game_params, [50, 100, 5000, 100000])
        self.assertEqual(self.room_model.max_player_count, 6)

        # Empty room_code
        self.room_model.on_reload([1, "2_room11", "_", [50, 100, 5000, 100000],
                                   6, 7, True, 2, 3, 2.5, 1])
        self.room_model.apply_changes()

        self.assertEqual(self.room_model.room_id, "1")
        self.assertEqual(self.room_model.game_config_model, game_config_model)
        self.assertEqual(self.room_model.game_config_model.ids, ["-1", "-1", "-1"])


class TestRoomSendMixIn:
    room = None
    player1 = None

    def test_send_player_joined_the_room(self):
        # Normal
        self.room.send_player_joined_the_room(self.player1, [self.player1])

        public_data = self.player1.export_public_data()
        for player in self.room.player_set:
            if player == self.player1:
                player.protocol.player_joined_the_room.assert_not_called()
            else:
                player.protocol.player_joined_the_room.assert_called_once_with(public_data)
            player.protocol.player_joined_the_room.reset_mock()

        # Without exclude_players
        self.room.send_player_joined_the_room(self.player1)

        for player in self.room.player_set:
            player.protocol.player_joined_the_room.assert_not_called()

    def test_send_player_joined_the_game(self):
        self.player1.place_index = 5

        self.room.send_player_joined_the_game(self.player1)

        public_data = self.player1.export_public_data()
        for player in self.room.player_set:
            player.protocol.player_joined_the_game.assert_called_once_with(5, public_data)

    def test_send_player_left_the_game(self):
        self.player1.place_index = 5

        self.room.send_player_left_the_game(self.player1)

        for player in self.room.player_set:
            player.protocol.player_left_the_game.assert_called_once_with(5)

    def test_send_player_left_the_room(self):
        self.player1.place_index = 5

        # Normal
        self.room.send_player_left_the_room(self.player1)

        for player in self.room.player_set:
            player.protocol.player_left_the_room.assert_called_once_with(5)
            player.protocol.player_left_the_room.reset_mock()

        # Using exclude_players
        self.room.send_player_left_the_room(self.player1, [self.player1])

        for player in self.room.player_set:
            if player == self.player1:
                player.protocol.player_left_the_room.assert_not_called()
            else:
                player.protocol.player_left_the_room.assert_called_once_with(5)

    def test_send_message(self):
        self.room.add_player(self.player1, "xxx")
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 10000))
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")

        self.do_test_send_message(self.room, self.room.player_set, self.player1)

    def test_send_message_without_receiver(self):
        self.room.add_player(self.player1, "xxx")
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 10000))
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")

        self.do_test_send_message_without_receiver(self.room, self.room.player_set, self.player1)

    # (Used to test room.send_message() and lobby.send_message())
    def do_test_send_message(self, target, player_set, sender):
        self.assertGreater(len(player_set), 0)

        # Public messages
        # (Chat)
        target.send_message(MessageType.MSG_TYPE_CHAT, "message text", sender, "456")

        for player in player_set:
            player.protocol.send_message.assert_called_once_with(
                MessageType.MSG_TYPE_CHAT, "message text", sender, "456")
            player.protocol.send_message.reset_mock()

        # (Public)
        target.send_message(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "message text", sender, "456")

        for player in player_set:
            player.protocol.send_message.assert_called_once_with(
                MessageType.MSG_TYPE_PUBLIC_SPOKEN, "message text", sender, "456")
            player.protocol.send_message.reset_mock()

        # Private messages
        # (Private)
        target.send_message(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "message text", sender, "456")

        for player in player_set:
            if player.user_id == "456":
                player.protocol.send_message.assert_called_once_with(
                    MessageType.MSG_TYPE_PRIVATE_SPOKEN, "message text", sender, "456")
            else:
                player.protocol.send_message.assert_not_called()
            player.protocol.send_message.reset_mock()

        # (Mail)
        target.send_message(MessageType.MSG_TYPE_MAIL, "message text", sender, "456")

        for player in player_set:
            if player.user_id == "456":
                player.protocol.send_message.assert_called_once_with(
                    MessageType.MSG_TYPE_MAIL, "message text", sender, "456")
            else:
                player.protocol.send_message.assert_not_called()
            player.protocol.send_message.reset_mock()

    def do_test_send_message_without_receiver(self, target, player_set, sender):
        self.assertGreater(len(player_set), 0)

        # Public messages
        # (Chat)
        target.send_message(MessageType.MSG_TYPE_CHAT, "message text", sender)

        for player in player_set:
            player.protocol.send_message.assert_called_once_with(
                MessageType.MSG_TYPE_CHAT, "message text", sender, -1)  # , "456")
            player.protocol.send_message.reset_mock()

        # (Public)
        target.send_message(MessageType.MSG_TYPE_PUBLIC_SPOKEN, "message text", sender)

        for player in player_set:
            player.protocol.send_message.assert_called_once_with(
                MessageType.MSG_TYPE_PUBLIC_SPOKEN, "message text", sender, -1)  # , "456")
            player.protocol.send_message.reset_mock()

        # Private messages
        # (Private)
        target.send_message(MessageType.MSG_TYPE_PRIVATE_SPOKEN, "message text", sender)

        for player in player_set:
            player.protocol.send_message.assert_not_called()
            player.protocol.send_message.reset_mock()

        # (Mail)
        target.send_message(MessageType.MSG_TYPE_MAIL, "message text", sender)

        for player in player_set:
            player.protocol.send_message.assert_not_called()
            player.protocol.send_message.reset_mock()

    def test_send_log(self):
        self.room.send_log("some text")

        for player in self.room.player_set:
            player.protocol.send_log.assert_called_once_with("some text")

    def test_send_ready_to_start(self):
        self.room.send_ready_to_start(5, True, 15)

        for player in self.room.player_set:
            player.protocol.ready_to_start.assert_called_once_with(5, True, 15)

    def test_send_reset_game(self):
        self.room.send_reset_game()

        for player in self.room.player_set:
            player.protocol.reset_game.assert_called_once_with()

    def test_send_change_player_turn(self):
        self.room.send_change_player_turn(3, 2.5)

        for player in self.room.player_set:
            player.protocol.change_player_turn.assert_called_once_with(3, 2.5)

    def test_send_player_wins(self):
        self.room.send_player_wins(2, 1000, 54000)

        for player in self.room.player_set:
            player.protocol.player_wins.assert_called_once_with(2, 1000, 54000)

    def test_send_player_wins_the_tournament(self):
        self.room.send_player_wins_the_tournament(2, 1000)

        for player in self.room.player_set:
            player.protocol.player_wins_the_tournament.assert_called_once_with(2, 1000)

    def test_send_update1(self):
        self.room.send_update1(1, 2, "3")

        for player in self.room.player_set:
            player.protocol.send_update1.assert_called_once_with(1, 2, "3")

    def test_send_update2(self):
        self.room.send_update2(1, 2, "3")

        for player in self.room.player_set:
            player.protocol.send_update2.assert_called_once_with(1, 2, "3")

    def test_send_raw_binary_update(self):
        self.room.send_raw_binary_update(b"raw_data")

        for player in self.room.player_set:
            player.protocol.raw_binary_update.assert_called_once_with(b"raw_data")


class TestRoom(TestCase, TestRoomSendMixIn):
    house_config = None
    room = None
    room2 = None
    player1 = None
    player2 = None
    player3 = None

    def setUp(self):
        # TestRoomSendMixIn.setUp(self)

        self.house_config = HouseConfig(data_dir_path="game_configs/")
        room_model = RoomModel(["1", "2_room11", "1_H_10_0", [50, 100, 5000, 100000],
                                0, -1, 6, 7, "xxx", "123", 2.5])
        room_model2 = RoomModel(["2", "2_room22", "1_H_10_0", [50, 100, 5000, 100000],
                                0, -1, 6, 7, "", "123", 2.5])
        self.room = Room(self.house_config, room_model)
        self.room2 = Room(self.house_config, room_model2)

        # Add players
        self.player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))

    def tearDown(self):
        # TestRoomSendMixIn.tearDown(self)
        self.house_config.dispose()

    def test_properties(self):
        self.room.room_model.max_player_count = 2

        # 0 playing
        self.assertEqual(self.room.has_free_seat_to_play, True)
        self.assertEqual(self.room.is_empty_room, True)

        # 1 playing
        player = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        self.room.add_player(player, "xxx")
        self.room.join_the_game(player, money_in_play=5000)  # , money_in_play=1000

        self.assertIsNotNone(player.game)
        self.assertEqual(self.room.has_free_seat_to_play, True)
        self.assertEqual(self.room.is_empty_room, False)

        # 2 playing
        player = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        self.room.add_player(player, "xxx")
        self.room.join_the_game(player, money_in_play=5000)  # , money_in_play=1000

        self.assertEqual(self.room.has_free_seat_to_play, False)
        self.assertEqual(self.room.is_empty_room, False)

        # 2 playing without limit
        self.room.room_model.max_player_count = -1

        self.assertEqual(self.room.has_free_seat_to_play, True)
        self.assertEqual(self.room.is_empty_room, False)

        # room_id
        self.assertEqual(self.room.room_id, self.room.room_model.room_id)
        self.assertEqual(self.room.room_id, "1")

        self.room.room_model = None

        self.assertEqual(self.room.room_id, None)

    def test_model_data(self):
        # Setter
        self.assertEqual(self.room.room_model.room_name, "2_room11")
        self.assertEqual(self.room.room_model.game_type, 10)
        self.assertEqual(self.room.room_model.min_stake, 50)

        self.room.model_data = [1, "new_2_room11", "1_1_21_0", [150, 100, 5000, 100000],
                                6, 7, "xxx", "123", 2.5]

        self.assertEqual(self.room.room_model.room_name, "new_2_room11")
        self.assertEqual(self.room.room_model.game_type, 21)
        self.assertEqual(self.room.room_model.min_stake, 150)

        # Getter
        self.room.room_model.room_name = "2_room11___"
        self.room.room_model.game_type = 32
        self.room.room_model.min_stake = 250

        model_data = self.room.model_data

        expected_data = [1, "2_room11___", "1_1_32_0", [250, 100, 5000, 100000],
                         6, 7, "xxx", "123", 2.5]
        self.assertEqual(model_data[:len(expected_data)], expected_data)

    def test_game_data(self):
        self.assertIsNone(self.room.game)

        game_data = [2, True, True, 3]
        self.room.game_data = game_data

        self.assertIsNotNone(self.room.game)
        self.assertEqual(self.room.game.room_id, "1")  # no setter
        self.assertEqual(self.room.game._is_in_progress, True)
        self.assertEqual(self.room.game._is_paused, True)
        self.assertEqual(self.room.game.game_elapsed_time, 3)

    def test_constructor(self):
        self.assertIsNotNone(self.room.logging)
        self.assertIsNotNone(self.room.house_config)
        self.assertIsNotNone(self.room.house_model)
        self.assertIsNotNone(self.room.room_model)
        self.assertIsNone(self.room.lobby)
        self.assertEqual(self.room.player_set, set())
        self.assertEqual(self.room.player_by_user_id, {})
        self.assertIsNone(self.room.game)

    def test_dispose(self):
        self.room.lobby = lobby = MagicMock()
        # self.room.game_data = [1, True, 1, 4, 3]
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 6000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 6000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 6000))
        self.room.add_player(player1, "xxx")
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")
        self.room.join_the_game(player1, money_in_play=6000)
        self.room.join_the_game(player2, money_in_play=5500)

        self.assertIsNotNone(player1.room)
        self.assertIsNotNone(player2.room)
        self.assertIsNotNone(player1.game)
        self.assertIsNotNone(player2.game)
        self.assertEqual(player1.money_amount, 0)
        self.assertEqual(player2.money_amount, 500)
        self.assertEqual(len(self.room.player_set), 3)
        self.assertEqual(len(self.room.game.player_list), 2)

        self.room.dispose()

        self.assertEqual(player1.money_amount, 6000)
        self.assertEqual(player2.money_amount, 6000)
        self.assertIsNone(player1.room)
        self.assertIsNone(player2.room)
        self.assertIsNone(player2.game)
        self.assertEqual(len(self.room.player_set), 0)
        self.assertIsNone(self.room.game)
        self.assertIsNone(self.room.lobby)
        self.assertIsNone(self.room.house_config)
        self.assertIsNone(self.room.house_model)
        self.assertIsNone(self.room.room_model)
        # self.assertIsNone(self.room.logging)

        # Ensure game.dispose called
        self.room.game = game = MagicMock()

        self.room.dispose()

        game.dispose.assert_called_once()

    def test_add_player(self):
        self.room.house_model.is_notify_each_player_joined_the_room = True
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 5000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 5000))
        player3 = utils.create_player(utils.create_user(self.house_config, "456", 5000))

        # player1

        # Wrong password
        result = self.room.add_player(player1)

        self.assertFalse(result)
        self.assertIsNone(player1.room)
        self.assertIsNone(self.room.game)
        self.assertEqual(len(self.room.player_set), 0)
        self.assertEqual(self.room.room_model.total_player_count, 0)
        player1.protocol.show_ok_message_dialog.assert_called_once_with(
            MessageCode.JOIN_ROOM_FAIL_TITLE, MessageCode.JOIN_ROOM_WRONG_PASSWORD)
        player1.protocol.reset_mock()

        # Add - OK
        result = self.room.add_player(player1, "xxx")

        self.assertTrue(result)
        self.assertIsNotNone(self.room.game)
        self.assertIsNotNone(player1.room)
        self.assertEqual(len(self.room.player_set), 1)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123"})
        self.assertEqual(self.room.room_model.total_player_count, 1)
        # (It's important to assert also an method order)
        self.assertEqual(player1.protocol.method_calls, [
            call.confirm_joined_the_room(self.room.room_model.export_public_data()),
            call.game_info(self.room.game.export_public_data(), [None] * 6)
        ])

        self.room.join_the_game(player1, 2, 5000)
        self.assertIsNotNone(player1.game)
        player1.protocol.reset_mock()

        # player2

        # Add another - OK
        result = self.room.add_player(player2, "xxx")

        self.assertTrue(result)
        self.assertIsNotNone(player2.room)
        self.assertEqual(len(self.room.player_set), 2)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 2)
        player_info_by_place_index = [None] * 6
        player_info_by_place_index[2] = player1.export_public_data()
        self.assertEqual(player2.protocol.method_calls, [
            call.confirm_joined_the_room(self.room.room_model.export_public_data()),
            call.game_info(self.room.game.export_public_data(), player_info_by_place_index)
        ])
        # (Assert player1 knows that player2 added)
        self.assertEqual(player1.protocol.method_calls, [
            call.player_joined_the_room(player2.export_public_data())
        ])
        player2.protocol.reset_mock()
        player1.protocol.reset_mock()

        # Add another again - OK
        result = self.room.add_player(player2, "xxx")

        self.assertTrue(result)
        self.assertIsNotNone(player2.room)
        self.assertEqual(len(self.room.player_set), 2)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 2)
        self.assertEqual(player2.protocol.method_calls, [
            call.confirm_joined_the_room(self.room.room_model.export_public_data()),
            call.game_info(self.room.game.export_public_data(), player_info_by_place_index)
        ])
        self.assertEqual(player1.protocol.method_calls, [])
        player1.protocol.reset_mock()
        player2.protocol.reset_mock()

        # player3
        # Adding another player with same user_id
        self.assertEqual(self.room.house_model.is_allow_multisession_in_the_room, False)

        result = self.room.add_player(player3, "xxx")

        self.assertFalse(result)
        self.assertIsNone(player3.room)
        self.assertEqual(len(self.room.player_set), 2)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 2)
        self.assertEqual(player3.protocol.method_calls, [
            # self.room.room_model.export_public_data(
            call.show_ok_message_dialog(MessageCode.JOIN_ROOM_FAIL_TITLE, MessageCode.JOIN_ROOM_FAIL_SAME_USER)
        ])
        self.assertEqual(player1.protocol.method_calls, [])
        player3.protocol.reset_mock()
        player1.protocol.reset_mock()

        # Adding another player with same user_id if it's enabled - OK
        self.room.house_model.is_allow_multisession_in_the_room = True

        result = self.room.add_player(player3, "xxx")

        self.assertTrue(result)
        self.assertIsNotNone(player3.room)
        self.assertEqual(len(self.room.player_set), 3)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 3)
        self.assertEqual(player3.protocol.method_calls, [
            call.confirm_joined_the_room(self.room.room_model.export_public_data()),
            call.game_info(self.room.game.export_public_data(), player_info_by_place_index)
        ])
        # is_notify_each_player_joined_the_room==True
        self.assertEqual(player1.protocol.method_calls, [
            call.player_joined_the_room(player3.export_public_data()),
        ])
        player3.protocol.reset_mock()
        player1.protocol.reset_mock()

        # Change room
        self.assertEqual(player1.room, self.room)
        self.room.remove_player = Mock(side_effect=self.room.remove_player)

        self.room2.add_player(player1)

        self.assertEqual(player1.room, self.room2)
        self.room.remove_player.assert_called_once_with(player1)

    def test_add_player_without_notifying_others(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))

        self.room.add_player(player1, "xxx")
        player1.protocol.reset_mock()
        # (Assert default)
        self.assertEqual(self.room.house_model.is_notify_each_player_joined_the_room, False)

        # Add 2nd player without notifying other players - OK
        result = self.room.add_player(player2, "xxx")

        # (Same calls)
        self.assertTrue(result)
        self.assertEqual(len(player2.protocol.method_calls), 2)
        # (No calls - no notifying)
        self.assertEqual(len(player1.protocol.method_calls), 0)

    def test__check_can_be_added(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        player3 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        self.room.add_player(player2, "xxx")

        self.assertEqual(set(self.room.player_by_user_id.keys()), {"456"})
        self.assertEqual(self.room.house_model.is_allow_multisession_in_the_room, False)

        # OK
        result = self.room._check_can_be_added(player1, "xxx")

        self.assertTrue(result)

        # Wrong password
        result = self.room._check_can_be_added(player1, "wrong")

        self.assertFalse(result)
        player1.protocol.show_ok_message_dialog.assert_called_once_with(
            MessageCode.JOIN_ROOM_FAIL_TITLE, MessageCode.JOIN_ROOM_WRONG_PASSWORD)
        player1.protocol.reset_mock()

        # OK - No password
        self.room.room_model.room_password = None

        result2 = self.room._check_can_be_added(player1, "")
        result3 = self.room._check_can_be_added(player1, "xxx")

        self.assertTrue(result2)
        self.assertTrue(result3)

        # Player with same user_id is added
        result2 = self.room._check_can_be_added(player2, "xxx")
        result3 = self.room._check_can_be_added(player3, "xxx")

        self.assertFalse(result2)
        self.assertFalse(result3)
        player2.protocol.show_ok_message_dialog.assert_called_once_with(
            MessageCode.JOIN_ROOM_FAIL_TITLE, MessageCode.JOIN_ROOM_FAIL_SAME_USER)
        player3.protocol.show_ok_message_dialog.assert_called_once_with(
            MessageCode.JOIN_ROOM_FAIL_TITLE, MessageCode.JOIN_ROOM_FAIL_SAME_USER)

        # OK - Adding player with same user_id enabled
        self.room.house_model.is_allow_multisession_in_the_room = True

        result2 = self.room._check_can_be_added(player2, "xxx")
        result3 = self.room._check_can_be_added(player3, "xxx")

        self.assertTrue(result2)
        self.assertTrue(result3)

    def test_remove_player(self):
        self.assertFalse(self.house_config.house_model.is_notify_each_player_joined_the_room)
        # self.room.leave_the_game = Mock()
        self.room._finish_game = Mock()

        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2.room = Mock()  # assume player is added to another room
        player2.game = Mock()
        player3 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        self.room.add_player(player1, "xxx")
        self.room.add_player(player3, "xxx")
        self.room.join_the_game(player1, money_in_play=5000)  # , money_in_play=1000

        self.assertIsNotNone(player1.room)
        self.assertIsNotNone(player1.game)
        self.assertEqual(player1.place_index, 0)
        self.assertEqual(len(self.room.player_set), 2)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 2)
        player1.protocol.reset_mock()
        player3.protocol.reset_mock()

        # Remove - OK
        result = self.room.remove_player(player1)

        self.assertTrue(result)
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertEqual(len(self.room.player_set), 1)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"456"})
        self.assertEqual(self.room.room_model.total_player_count, 1)
        # self.room.leave_the_game.assert_called_once_with(player1)
        self.room._finish_game.assert_not_called()
        # self.room.leave_the_game.reset_mock()
        player1.protocol.player_left_the_game.assert_called_once_with(0)
        player1.protocol.confirm_left_the_room.assert_called_once_with()
        player1.protocol.send_log.assert_called_once()
        player1.protocol.update_self_user_info.assert_called_once_with(player1.user.export_public_data())
        player3.protocol.player_left_the_game.assert_called_once_with(0)
        player3.protocol.send_log.assert_called_once()
        self.assertEqual(len(player1.protocol.method_calls), 4)
        self.assertEqual(len(player3.protocol.method_calls), 2)
        player1.protocol.reset_mock()
        player3.protocol.reset_mock()

        # Remove with notifying other players - OK
        self.house_config.house_model.is_notify_each_player_joined_the_room = True
        self.room.add_player(player1, "xxx")
        player1.protocol.reset_mock()
        player3.protocol.reset_mock()

        result = self.room.remove_player(player1)

        self.assertTrue(result)
        self.assertEqual(player1.protocol.method_calls, [
            call.confirm_left_the_room()
        ])
        self.assertEqual(player3.protocol.method_calls, [
            call.player_left_the_room(player1.export_public_data())
        ])
        player1.protocol.reset_mock()
        player3.protocol.reset_mock()

        # Again
        result = self.room.remove_player(player1)

        self.assertFalse(result)
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertEqual(self.room.room_model.total_player_count, 1)
        # self.room.leave_the_game.assert_not_called()
        self.room._finish_game.assert_not_called()
        self.assertEqual(player1.protocol.method_calls, [])
        self.assertEqual(player3.protocol.method_calls, [])

        # Remove not added
        result = self.room.remove_player(player2)

        self.assertFalse(result)
        self.assertIsNotNone(player2.room)
        self.assertIsNotNone(player2.game)
        self.assertEqual(self.room.room_model.total_player_count, 1)
        # self.room.leave_the_game.assert_not_called()
        self.room._finish_game.assert_not_called()

        # Remove the last - OK
        result = self.room.remove_player(player3)

        self.assertTrue(result)
        self.assertIsNone(player3.room)
        self.assertIsNone(player3.game)
        self.assertEqual(len(self.room.player_set), 0)
        self.assertEqual(self.room.player_by_user_id, {})
        self.assertEqual(self.room.room_model.total_player_count, 0)
        # self.room.leave_the_game.assert_called_once_with(player1)
        self.room._finish_game.assert_called_once()
        # self.room.leave_the_game.reset_mock()

    def test_remove_all_players(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        self.room.add_player(player1, "xxx")
        self.room.add_player(player2, "xxx")

        self.assertIsNotNone(player1.room)
        self.assertIsNotNone(player2.room)
        self.assertEqual(len(self.room.player_set), 2)
        self.assertEqual(set(self.room.player_by_user_id.keys()), {"123", "456"})
        self.assertEqual(self.room.room_model.total_player_count, 2)

        self.room.remove_all_players()

        self.assertIsNone(player1.room)
        self.assertIsNone(player2.room)
        self.assertEqual(len(self.room.player_set), 0)
        self.assertEqual(self.room.player_by_user_id, {})
        self.assertEqual(self.room.room_model.total_player_count, 0)

    def test_get_game_info(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 10000))
        self.room.add_player(player1, "xxx")
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")
        self.room.join_the_game(player1, money_in_play=5000)  # , money_in_play=1000
        self.room.join_the_game(player2, 2, 5000)
        self.assertIsNotNone(player1.game)
        self.assertIsNotNone(player2.game)
        player2.protocol.reset_mock()
        player3.protocol.reset_mock()

        # Player in game
        self.room.get_game_info(player2)

        self.assertEqual(player2.protocol.method_calls, [
            call.game_info(self.room.game.export_public_data_for(2), None)
        ])

        # Player in game (is_get_room_content)
        player2.protocol.reset_mock()

        self.room.get_game_info(player2, True)

        player_info_by_place_index = [None] * 6
        player_info_by_place_index[0] = player1.export_public_data()
        player_info_by_place_index[2] = player2.export_public_data()
        self.assertEqual(player2.protocol.method_calls, [
            call.game_info(self.room.game.export_public_data_for(2), player_info_by_place_index)
        ])

        # Not in game
        self.room.get_game_info(player3)

        self.assertEqual(player3.protocol.method_calls, [
            call.game_info(self.room.game.export_public_data(), None)
        ])

        # Not in game (is_get_room_content)
        player3.protocol.reset_mock()

        self.room.get_game_info(player3, True)

        self.assertEqual(player3.protocol.method_calls, [
            call.game_info(self.room.game.export_public_data(), player_info_by_place_index)
        ])

    def test_join_the_game(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 10000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 10000))
        player4 = utils.create_player(utils.create_user(self.house_config, "246", 10000))
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")
        self.room.add_player(player4, "xxx")

        # Joining
        result = self.room.join_the_game(player1, money_in_play=5000)  # , money_in_play=1000

        self.assertFalse(result)
        self.assertIsNone(player1.game)
        self.assertEqual(self.room.room_model.playing_count, 0)

        # Join - OK
        result = self.room.join_the_game(player2, 2, 5000)

        self.assertTrue(result)
        self.assertIsNotNone(player2.game)
        self.assertEqual(player2.place_index, 2)
        self.assertEqual(player2.money_in_play, 5000)
        self.assertEqual(self.room.room_model.playing_count, 1)
        self.assertEqual(self.room.game.max_player_count, 6)

        # Join another - OK
        result = self.room.join_the_game(player3, money_in_play=5000)  # , money_in_play=1000

        self.assertTrue(result)
        self.assertIsNotNone(player3.game)
        self.assertEqual(player3.place_index, 0)
        self.assertEqual(player3.money_in_play, 5000)
        self.assertEqual(self.room.room_model.playing_count, 2)
        self.assertEqual(self.room.game.max_player_count, 6)

        # Out of max count
        self.room.room_model.max_player_count = 2
        result = self.room.join_the_game(player4, money_in_play=5000)  # , money_in_play=1000

        self.assertFalse(result)
        self.assertIsNone(player4.game)
        self.assertEqual(player4.place_index, -1)
        self.assertEqual(player4.money_in_play, 0)
        self.assertEqual(self.room.room_model.playing_count, 2)
        self.assertEqual(self.room.game.max_player_count, 2)

        # Ensure game.add_player called
        self.room.game.add_player = Mock()

        self.room.join_the_game(player4, money_in_play=5000)  # , money_in_play=1000

        self.room.game.add_player.assert_called_once_with(player4, -1, 5000)

    def test_leave_the_game(self):
        player1 = utils.create_player(utils.create_user(self.house_config, "123", 10000))
        player2 = utils.create_player(utils.create_user(self.house_config, "456", 9000))
        player3 = utils.create_player(utils.create_user(self.house_config, "789", 6000))
        player4 = utils.create_player(utils.create_user(self.house_config, "246", 10000))
        self.room.add_player(player2, "xxx")
        self.room.add_player(player3, "xxx")
        self.room.add_player(player4, "xxx")
        self.room.join_the_game(player2, 1, 5000)
        self.room.join_the_game(player3, money_in_play=6000)  # , money_in_play=1000
        self.assertIsNotNone(player2.game)
        self.assertIsNotNone(player3.game)

        # Leaving
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertEqual(self.room.room_model.playing_count, 2)

        result = self.room.leave_the_game(player1)

        self.assertFalse(result)
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertEqual(self.room.room_model.playing_count, 2)

        # Leave - OK
        self.assertIsNotNone(player2.game)
        self.assertEqual(player2.place_index, 1)
        self.assertEqual(player2.money_in_play, 5000)
        self.assertEqual(player2.user.money_amount, 4000)

        result = self.room.leave_the_game(player2)

        self.assertTrue(result)
        self.assertIsNone(player2.game)
        self.assertEqual(player2.place_index, -1)
        self.assertEqual(player2.money_in_play, 0)
        self.assertEqual(player2.user.money_amount, 9000)
        self.assertEqual(self.room.room_model.playing_count, 1)

        # Leave another - OK
        self.assertIsNotNone(player3.game)
        self.assertEqual(player3.place_index, 0)
        self.assertEqual(player3.money_in_play, 6000)
        self.assertEqual(player3.user.money_amount, 0)

        result = self.room.leave_the_game(player3)

        self.assertTrue(result)
        self.assertIsNone(player3.game)
        self.assertEqual(player3.place_index, -1)
        self.assertEqual(player3.money_in_play, 0)
        self.assertEqual(player3.user.money_amount, 6000)
        self.assertEqual(self.room.room_model.playing_count, 0)

        # Ensure game.remove_player called
        self.room.game.remove_player = Mock()

        self.room.leave_the_game(player4)

        self.room.game.remove_player.assert_called_once_with(player4)

    def test_create_game(self):
        self.assertIsNone(self.room.game)

        self.room._create_game()

        self.assertIsNotNone(self.room.game)
        self.assertIsInstance(self.room.game, Game)
        self.assertEqual(self.room.game.room, self.room)

        # Call again
        game = self.room.game

        self.room._create_game()

        self.assertEqual(self.room.game, game)

    def test_finish_game(self):
        self.assertIsNone(self.room.game)

        # No exception
        self.room._finish_game()

        # Normal
        self.room.game = game = MagicMock()

        self.room._finish_game()

        game.dispose.assert_called_once()
        self.assertIsNone(self.room.game)

    def test_dispose_game(self):
        self.assertIsNone(self.room.game)

        # No exception
        self.room._dispose_game()

        # Normal
        self.room.game = game = MagicMock()

        self.room._dispose_game()

        game.dispose.assert_called_once()
        self.assertIsNone(self.room.game)
