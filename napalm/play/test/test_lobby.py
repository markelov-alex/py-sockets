from unittest import TestCase
from unittest.mock import call, Mock

from napalm.core import BaseModel
from napalm.play.core import HouseConfig
from napalm.play.house import User
from napalm.play.lobby import Lobby, RoomModel, Room, LobbyModel
from napalm.play.protocol import FindAndJoin
from napalm.play.test import utils
from napalm.play.test.test_lobby_room import TestRoomSendMixIn


"""
These test are more system tests than unit test, that's why they are a bit excess
(we always test what protocol will receive, but not always what method was called).
"""

class Asserts:
    """
    To remove warnings
    """
    assertEqual = None
    assertNotEqual = None
    assertIsNone = None
    assertIsNotNone = None
    assertIn = None
    assertNotIn = None
    assertTrue = None
    assertFalse = None
    assertRaises = None


class TestLobbyModel(TestCase):
    house_config = None
    lobby_model = None

    def setUp(self):
        super().setUp()
        house_config = HouseConfig(house_id=0,data_dir_path="initial_configs/")
        self.lobby_model = house_config.house_model.lobby_model_by_id["1"]

    def test_available_room_models(self):
        self.assertEqual(len(self.lobby_model.available_room_models), 6)

        self.lobby_model.available_room_models[0].is_marked_deleted = True
        self.lobby_model.available_room_models[1].is_marked_for_delete = True

        self.assertEqual(len(self.lobby_model.available_room_models), 4)

        Room.is_available_if_deleting = True

        self.assertEqual(len(self.lobby_model.available_room_models), 5)

    # See also test_house_config
    def test_constructor(self):
        self.assertEqual(self.lobby_model.lobby_id, "1")
        self.assertEqual(self.lobby_model.lobby_name, "Lobby 1")
        self.assertIsNotNone(self.lobby_model.rooms)
        self.assertEqual(len(self.lobby_model.room_model_list), 6)
        self.assertEqual(len(self.lobby_model.room_model_by_id), 6)

        # Empty
        lobby_model = LobbyModel()

        self.assertIsNone(lobby_model.lobby_id)
        self.assertEqual(lobby_model.lobby_name, "")
        self.assertIsNone(lobby_model.rooms)
        self.assertEqual(lobby_model.room_model_list, [])
        self.assertEqual(lobby_model.room_model_by_id, {})

        # Assert properties
        lobby_model = LobbyModel(["11", "name11", [["1"], [2]]])

        self.assertEqual(lobby_model.lobby_id, "11")
        self.assertEqual(lobby_model.lobby_name, "name11")
        self.assertEqual(lobby_model.rooms, [["1"], [2]])

    def test_on_reload(self):
        RoomModel.get_model_by_id("extra1").room_name = "extra1_room_changed"
        self.assertEqual(len(self.lobby_model.room_model_list), 6)
        self.assertEqual(len(self.lobby_model.room_model_by_id), 6)
        self.assertEqual(len(self.lobby_model.available_room_models), 6)
        self.assertEqual(self.lobby_model.room_model_by_id["1"].room_name, "1_room1")
        self.assertEqual(self.lobby_model.room_model_by_id["2"].room_name, "1_room2")
        self.assertEqual(self.lobby_model.room_model_by_id["extra1"].room_name, "extra1_room")
        self.assertNotIn("55", self.lobby_model.room_model_by_id)

        self.lobby_model.on_reload({"rooms": ["extra1", "extra2", [1, "1_room1_changed"], ["2", "1_room2_changed"],
                                              ["55", "1_room55"]]})

        self.assertEqual(len(self.lobby_model.room_model_list), 6)
        self.assertEqual(len(self.lobby_model.room_model_by_id), 6)
        self.assertEqual(len(self.lobby_model.available_room_models), 5)
        self.assertEqual(self.lobby_model.room_model_by_id["1"].room_name, "1_room1_changed")
        self.assertEqual(self.lobby_model.room_model_by_id["2"].room_name, "1_room2_changed")
        self.assertEqual(self.lobby_model.room_model_by_id["extra1"].room_name, "extra1_room_changed")
        self.assertIn("55", self.lobby_model.room_model_by_id)


class TestRoomManager(Asserts):
    house_config = None
    lobby = None
    user1 = None
    player1 = None
    user2 = None
    player2 = None
    player3 = None

    def test_rooms_data(self):
        user_owner = self.user1
        player_owner = self.player1
        private_room_info = [12, "12_room", "1_H_10_2", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(private_room_info, player_owner)

        # Getter
        rooms_data = self.lobby.rooms_data
        self.assertEqual(set(rooms_data.keys()), {"1", "12", "2", "3", "4", "extra1", "extra2"})
        self.assertEqual(rooms_data["1"][1], "1_room1")
        self.assertEqual(rooms_data["12"][1], "12_room")

        # Setter
        rooms_data["1"][1] = "1_room1_changed"
        self.lobby.rooms_data = rooms_data

        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "12", "2", "3", "4", "extra1", "extra2"})
        self.assertEqual(self.lobby.room_by_id["1"].room_name, "1_room1_changed")

        # Setter doesn't delete models, but only updates existing
        self.lobby.rooms_data = {}

        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "12", "2", "3", "4", "extra1", "extra2"})

        # Setter can create new model
        self.lobby.rooms_data = {"5": ["5", "5 room", "1_H_10_2", [50, 100, 5000, 100000], 0, -1, 6]}

        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "12", "2", "3", "4", "5", "extra1", "extra2"})

    def test_constructor(self):
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "2", "3", "4", "extra1", "extra2"})
        self.assertEqual(self.lobby.room_by_id.keys(), self.lobby.lobby_model.available_room_models)
        self.assertEqual(set(self.lobby.room_list), set(self.lobby.room_by_id))

    def test_dispose(self):
        self.assertIsNotNone(self.lobby.house_config)
        self.assertIsNotNone(self.lobby.lobby_model)
        self.assertEqual(len(self.lobby.room_by_id), 6)
        self.assertEqual(len(self.lobby.room_list), 6)
        for room in self.lobby.room_list:
            room.dispose = Mock()
        room_list = self.lobby.room_list

        self.lobby.dispose()

        self.assertIsNone(self.lobby.house_config)
        self.assertIsNone(self.lobby.lobby_model)
        self.assertEqual(len(self.lobby.room_by_id), 0)
        self.assertEqual(len(self.lobby.room_list), 0)
        for room in room_list:
            room.dispose.assert_called_once()

    def test_rooms_export_public_data(self):
        # Normal
        data = self.lobby.rooms_export_public_data()

        self.assertEqual(len(data), 6)
        self.assertEqual(data[0][0], "1")
        self.assertEqual(data[0], self.lobby.room_list[0].room_model.export_public_data())

        # Consider private
        user_owner = User(self.house_config, "123")
        player_owner = user_owner.on_connect()
        user2 = User(self.house_config, "456")
        player2 = user2.on_connect()
        # "2" in "1_H_10_2" means private
        private_room_info = [12, "12_room11", "1_H_10_2", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(private_room_info, player_owner)

        self.assertEqual(len(self.lobby.rooms_export_public_data()), 6)
        self.assertEqual(len(self.lobby.rooms_export_public_data(player2)), 6)
        self.assertEqual(len(self.lobby.rooms_export_public_data(player_owner)), 7)

    def test_create_room_protected(self):
        self.assertEqual(len(self.lobby.room_by_id), 6)
        self.assertEqual(len(self.lobby.room_list), 6)

        # Create normal
        room_info = [12, "12_room", "1_H_10_0", [50, 100, 5000, 100000], 6]

        result = self.lobby._create_room(room_info)

        self.assertEqual(result.room_id, "12")
        self.assertEqual(result.room_name, "12_room")
        self.assertEqual(result.room_model.room_name, "12_room")
        self.assertEqual(result.owner_user_id, None)
        self.assertEqual(result.room_model.is_private, False)
        self.assertEqual(result.lobby, self.lobby)
        self.assertIn(result, self.lobby.room_list)
        self.assertEqual(len(self.lobby.room_by_id), 7)
        self.assertEqual(len(self.lobby.room_list), 7)
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "12", "2", "3", "4", "extra1", "extra2"})
        # test sorting

        # Create private
        user_owner = self.user1
        player_owner = self.player1
        room_info = [15, "15_room", "1_H_10_0", [50, 100, 5000, 100000], 6]

        result = self.lobby._create_room(room_info, player_owner)

        self.assertEqual(result.room_id, "15")
        self.assertEqual(result.room_name, "15_room")
        self.assertEqual(result.room_model.room_name, "15_room")
        self.assertEqual(result.owner_user_id, "123")
        self.assertEqual(result.room_model.is_private, True)
        self.assertEqual(result.lobby, self.lobby)
        self.assertIn(result, self.lobby.room_list)
        self.assertEqual(len(self.lobby.room_by_id), 8)
        self.assertEqual(len(self.lobby.room_list), 8)
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"1", "12", "15", "2", "3", "4", "extra1", "extra2"})
        # Assert room_list sorting
        self.assertEqual([room.room_id for room in self.lobby.room_list],
                         ["1", "2", "3", "4", "12", "15", "extra1", "extra2"])

        # Create with id existing in lobby_model
        room_info = ["1", "1_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room(room_info)

        self.assertEqual(result.room_id, "0")
        self.assertEqual(result.room_name, "1_room")
        self.assertEqual(result.room_model.room_name, "1_room")
        self.assertEqual(len(self.lobby.room_list), 9)
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"0", "1", "12", "15", "2", "3", "4", "extra1", "extra2"})

        # Create with id same as created before
        room_info = [15, "15_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room(room_info)

        self.assertEqual(result.room_id, "16")
        self.assertEqual(result.room_name, "15_room")
        self.assertEqual(result.room_model.room_name, "15_room")
        self.assertEqual(len(self.lobby.room_list), 10)
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"0", "1", "12", "15", "16", "2", "3", "4", "extra1", "extra2"})

        # Create with id same as created before by model
        room_info = [15, "15_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        room_model = self.lobby._create_room_model(room_info)
        result = self.lobby._create_room(room_model)

        self.assertEqual(result, None)
        # Same
        self.assertEqual(len(self.lobby.room_list), 10)
        self.assertEqual(set(self.lobby.room_by_id.keys()), {"0", "1", "12", "15", "16", "2", "3", "4", "extra1", "extra2"})

        # Create with empty id and by model
        room_info = [None, "None_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        room_model = self.lobby._create_room_model(room_info)
        result = self.lobby._create_room(room_model)

        self.assertEqual(result.room_model, room_model)
        self.assertEqual(result.room_id, "6")
        self.assertEqual(result.room_name, "None_room")
        self.assertEqual(result.room_model.room_name, "None_room")
        self.assertEqual(len(self.lobby.room_list), 11)
        self.assertEqual(set(self.lobby.room_by_id.keys()),
                         {"0", "1", "12", "15", "16", "2", "3", "4", "5", "extra1", "extra2"})
        # Assert room_list sorting
        self.assertEqual([room.room_id for room in self.lobby.room_list],
                         ["0", "1", "2", "3", "4", "5", "12", "15", "16", "extra1", "extra2"])

    def test_create_room_model(self):
        # By model as argument
        model = RoomModel()

        result = self.lobby._create_room_model(model)

        self.assertEqual(result, model)

        # By another model as argument
        model = BaseModel(None)

        with self.assertRaises(Exception):
            self.lobby._create_room_model(model)

        # Create by dict
        room_info = {"room_id": 0, "room_name": "room00"}
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "0")
        self.assertEqual(result.room_name, "room00")

        # Create with empty id
        room_info = [None, "None_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "0")
        self.assertEqual(result.room_name, "None_room")

        # Create with existed id
        room_info = [1, "room 1", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "5")
        self.assertEqual(result.room_name, "room 1")

        # Create again (_create_room_model doesn't make changes in lobby)
        room_info = [1, "room_1", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "5")
        self.assertEqual(result.room_name, "room_1")

        # Create with existed string id
        room_info = ["1", "room01", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "0")
        self.assertEqual(result.room_name, "room01")

        # Create with existed not digital string id
        room_info = ["extra1", "room_extra1", "1_H_10_0", [50, 100, 5000, 100000], 6]
        result = self.lobby._create_room_model(room_info)

        self.assertEqual(result.room_id, "0")
        self.assertEqual(result.room_name, "room_extra1")

    def test_dispose_room(self):
        user_owner = self.user1
        player_owner = self.player1

        # Disposing empty room_id
        result = self.lobby._dispose_room(None, None)

        self.assertFalse(result)

        # Disposing not existing room
        self.assertNotIn("9", self.lobby.room_by_id)

        result = self.lobby._dispose_room(player_owner, "9")

        self.assertFalse(result)

        # Disposing not own room
        self.assertIn("1", self.lobby.room_by_id)
        room = self.lobby.room_by_id["1"]
        room.dispose = Mock()

        result = self.lobby._dispose_room(player_owner, "1")

        self.assertFalse(result)
        room.dispose.assert_not_called()

        # Dispose own room
        room_info = [15, "15_room", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner)
        self.assertIn("15", self.lobby.room_by_id)
        room = self.lobby.room_by_id["15"]
        room.dispose = Mock()

        result = self.lobby._dispose_room(player_owner, "1")

        self.assertTrue(result)
        self.assertNotIn("15", self.lobby.room_by_id)
        room.dispose.assert_called_once()

    def test_remove_room(self):
        user1 = self.user1
        player1 = self.player1
        user2 = self.user2
        player2 = self.player2

        # No exception
        self.lobby.remove_room(None)

        # Use room_id from lobby.room_by_id, but wrong instance
        self.assertIn("1", self.lobby.room_by_id)
        room = Room(None, RoomModel(["1", "name"]))
        self.assertEqual(room.room_id, "1")

        self.lobby.remove_room(room)

        self.assertIn("1", self.lobby.room_by_id)

        # Remove
        room = self.lobby.room_by_id["1"]
        room.join_the_game(player1)  # , money_in_play=1000
        room.join_the_game(player2)  # , money_in_play=1000
        room.dispose = Mock()
        self.assertEqual(room.lobby, self.lobby)
        self.assertIn(room, self.lobby.room_list)
        self.assertEqual(len(room.player_set), 2)

        self.lobby.remove_room(room)

        self.assertIsNone(room.lobby)
        self.assertNotIn(room, self.lobby.room_list)
        self.assertNotIn("1", self.lobby.room_by_id)
        self.assertNotIn(room, self.lobby.room_by_id.values())
        # (We can remove room from lobby keeping players playing)
        self.assertEqual(len(room.player_set), 2)
        room.dispose.assert_not_called()

    def test_create_room(self):
        user1 = self.user1
        player1 = self.player1

        # OK
        self.assertNotIn("0", self.lobby.room_by_id)

        self.lobby.create_room(player1, [1, "player1_room_name"])

        self.assertIn("0", self.lobby.room_by_id)
        room = self.lobby.room_by_id["0"]
        self.assertEqual(room.room_name, "player1_room_name")
        player1.protocol.room_info.assert_called_once_with(room.export_public_data())
        player1.protocol.room_info.reset_mock()

        # Fail
        self.assertIn("1", self.lobby.room_by_id)

        self.lobby.create_room(player1, RoomModel([1, "player1_room_name"]))

        player1.protocol.room_info.assert_called_once_with(None)

    def test_edit_room(self):
        user_owner0 = self.user1
        player_owner0 = self.player1
        user_owner = self.user2
        player_owner = self.player2

        # Cannot change room of no owner
        self.assertIn("1", self.lobby.room_by_id)

        self.lobby.edit_room(player_owner, [1, "player_room_name"])

        room = self.lobby.room_by_id["1"]
        self.assertNotEqual(room.room_name, "player_room_name")
        player_owner.protocol.room_info.assert_called_once_with(None)
        player_owner.protocol.room_info.reset_mock()

        # Cannot change room of another owner
        self.assertNotIn("10", self.lobby.room_by_id)
        room_info = [10, "room_name", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner0)
        self.assertIn("10", self.lobby.room_by_id)
        room = self.lobby.room_by_id["10"]
        self.assertEqual(room.room_name, "room_name")

        self.lobby.edit_room(player_owner, ["10", "player_room_name"])

        self.assertNotEqual(room.room_name, "player_room_name")
        player_owner.protocol.room_info.assert_called_once_with(None)
        player_owner.protocol.room_info.reset_mock()

        # Edit
        self.assertNotIn("11", self.lobby.room_by_id)
        room_info = [11, "room_name", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner)
        self.assertIn("11", self.lobby.room_by_id)
        room = self.lobby.room_by_id["11"]
        self.assertEqual(room.room_name, "room_name")

        self.lobby.edit_room(player_owner, [11, "player_room_name"])

        self.assertEqual(room.room_name, "player_room_name")
        player_owner.protocol.room_info.assert_called_once_with(room.export_public_data())
        player_owner.protocol.room_info.reset_mock()

    def test_delete_room(self):
        user_owner0 = self.user1
        player_owner0 = self.player1
        user_owner = self.user2
        player_owner = self.player2

        # Cannot change room of no owner
        self.assertIn("1", self.lobby.room_by_id)

        self.lobby.delete_room(player_owner, "1")

        room = self.lobby.room_by_id["1"]
        self.assertIn("1", self.lobby.room_by_id)
        player_owner.protocol.rooms_list.assert_not_called()

        # Cannot change room of another owner
        self.assertNotIn("10", self.lobby.room_by_id)
        room_info = [10, "room_name", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner0)
        self.assertIn("10", self.lobby.room_by_id)

        self.lobby.delete_room(player_owner, "10")

        self.assertIn("10", self.lobby.room_by_id)
        player_owner.protocol.rooms_list.assert_not_called()

        # Delete
        self.assertNotIn("11", self.lobby.room_by_id)
        room_info = [11, "room_name", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner)
        self.assertIn("11", self.lobby.room_by_id)

        self.lobby.delete_room(player_owner, "11")

        self.assertNotIn("11", self.lobby.room_by_id)
        player_owner.protocol.rooms_list.assert_called_once_with(self.lobby.rooms_export_public_data(player_owner))
        self.assertEqual(len(player_owner.protocol.rooms_list.call_args[0][0]), 6)

    def test_get_room_list(self):
        user_owner0 = self.user1
        player_owner0 = self.player1
        user_owner = self.user2
        player_owner = self.player2

        # Create private room
        self.assertNotIn("11", self.lobby.room_by_id)
        room_info = [11, "room_name", "1_H_10_2", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner0)
        self.assertIn("11", self.lobby.room_by_id)
        # Create public room
        self.assertNotIn("12", self.lobby.room_by_id)
        room_info = ["12", "room_name", "1_H_10_0", [50, 100, 5000, 100000], 6]
        self.lobby._create_room(room_info, player_owner0)
        self.assertIn("12", self.lobby.room_by_id)

        # Get room list for owner
        self.lobby.get_room_list(player_owner0)

        player_owner0.protocol.rooms_list.assert_called_once_with(self.lobby.rooms_export_public_data(player_owner0))
        self.assertEqual(len(self.lobby.rooms_export_public_data(player_owner0)), 8)
        self.assertEqual(len(player_owner0.protocol.rooms_list.call_args[0][0]), 8)

        # Get room list for anyone
        self.lobby.get_room_list(player_owner)

        player_owner.protocol.rooms_list.assert_called_once_with(self.lobby.rooms_export_public_data(player_owner))
        self.assertEqual(len(self.lobby.rooms_export_public_data(player_owner)), 7)
        self.assertEqual(len(player_owner.protocol.rooms_list.call_args[0][0]), 7)

    def test_find_free_room(self):
        user1 = self.user1
        player1 = self.player1
        user2 = self.user2
        user2.money_amount = 5000
        player2 = self.player2
        user3 = utils.create_user(self.house_config, "789")
        player3 = utils.create_player(user3)

        user_id = 0
        for room in self.lobby.room_list:
            for index in range(room.room_model.max_player_count - 1):
                user = User(str(user_id))
                player = user.on_connect()
                room.join_the_game(player)  # , money_in_play=1000
                user_id += 1

        # room_id of "1_H_10_0":
        #  max_stake=50: "extra1", "1", "4"
        #  max_stake=100: "extra2", "3"

        # JOIN_GAME
        self.lobby.find_free_room(player1, FindAndJoin.JOIN_GAME, 1, "H", 10, 0, 100)

        self.assertEqual(player1.room.room_id, "extra2")
        self.assertIsNotNone(player1.game)
        # max_buy_in=10000
        self.assertEqual(player1.money_in_play, 10000)
        player1.protocol.method_calls = [
            call.confirm_joined_the_room(player1.room.room_model.export_public_data()),
            call.player_joined_the_game(player1.place_index, player1.export_public_data())
        ]

        # JOIN_ROOM
        self.lobby.find_free_room(player2, FindAndJoin.JOIN_ROOM, 1, "H", 10, 0, 100)

        self.assertEqual(player2.room.room_id, "3")
        self.assertIsNone(player2.game)
        player2.protocol.method_calls = [
            call.confirm_joined_the_room(player2.room.room_model.export_public_data())
        ]

        # JUST_FIND
        self.lobby.find_free_room(player3, FindAndJoin.JUST_FIND, 1, "H", 10, 0, 100)

        self.assertIsNone(player3.room)
        self.assertIsNone(player3.game)
        player3.protocol.game_info.assert_called_once()
        args = player3.protocol.game_info.call_args[0]
        # game_info (the only free room is left with such parameters is with room_id="3" in which player2 just joined)
        self.assertEqual(args[0], player2.room.game.export_public_data())
        # player_info_list
        self.assertEqual(len(args[1]), 6)

        # JOIN_GAME after JOIN_ROOM
        self.lobby.find_free_room(player2, FindAndJoin.JOIN_GAME, 1, "H", 10, 0, 100)

        # user2.money_amount=5000, max_buy_in=10000
        self.assertEqual(player2.money_in_play, 5000)

        # JUST_FIND - with no free room
        self.lobby.find_free_room(player3, FindAndJoin.JUST_FIND, 1, "H", 10, 0, 100)

        self.assertIsNone(player3.room)
        self.assertIsNone(player3.game)
        player3.protocol.game_info.assert_called_once()
        args = player3.protocol.game_info.call_args[0]
        self.assertEqual(args[0], None)
        self.assertEqual(args[1], None)

    def test_find_free_room_among_full_rooms(self):
        player1 = self.player1

        self.lobby.get_game_info = Mock()
        self.lobby.join_the_room = Mock()
        self.lobby.join_the_game = Mock()

        user_id = 0
        for room in self.lobby.room_list:
            for index in range(room.room_model.max_player_count):
                user = User(str(user_id))
                player = user.on_connect()
                room.join_the_game(player)  # , money_in_play=1000
                user_id += 1

        # No free room
        self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND)

        self.lobby.get_game_info.assert_called_with(player1, -1)

        # One free place in single free room
        # Just find and give info
        self.assertEqual(self.lobby.room_list[1].room_id, "2")
        self.lobby.room_list[1].remove_player()

        self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND)

        self.lobby.get_game_info.assert_called_with(player1, "2")

        # Join the room
        self.lobby.find_free_room(player1, FindAndJoin.JOIN_ROOM)

        self.lobby.join_the_room.assert_called_with(player1, "2")

        # Join the game
        self.lobby.find_free_room(player1, FindAndJoin.JOIN_GAME)

        self.lobby.join_the_game.assert_called_with(player1, "2")

        # Empty room is chosen only if all other rooms are full
        self.assertEqual(self.lobby.room_list[0].room_id, "1")
        self.lobby.room_list[0].remove_all_players()

        self.lobby.find_free_room(player1, FindAndJoin.JOIN_GAME)

        self.lobby.join_the_game.assert_called_with(player1, "2")

        # Only empty room available, choose empty room
        user = utils.create_user(self.house_config, "4444")
        player = utils.create_player(user)
        self.lobby.room_list[1].join_the_game(player)  # , money_in_play=1000

        self.lobby.find_free_room(player1, FindAndJoin.JOIN_GAME)

        self.lobby.join_the_game.assert_called_with(player1, "1")

    def test_find_free_room_by_params(self):
        player1 = self.player1

        self.lobby.get_game_info = Mock()
        # self.lobby.join_the_room = Mock()
        # self.lobby.join_the_game = Mock()

        # Full up "extra1" room with players
        user_id = 0
        for room in self.lobby.room_list:
            if room.room_id in ["extra1"]:
                for index in range(room.room_model.max_player_count):
                    user = User(str(user_id))
                    player = user.on_connect()
                    room.join_the_game(player)  # , money_in_play=1000
                    user_id += 1

        # room_id of "1_H_10_0":
        #  max_stake=50: "extra1", "1", "4"
        #  max_stake=100: "extra2", "3"
        # room_id of "1_H_40_0":
        #  max_stake=50: "2"

        # Wrong params
        # No such a game_id
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 2)

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # No such a game_variation
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "O")

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # No such a game_type
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "O", 20)

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # No such a room_type
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "O", 10, 2)

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # No such a max_stake
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "O", 10, 0, 200)

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # No such a max_stake
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "H", 40, 0, 100)

        self.assertIsNone(result)
        self.lobby.get_game_info.assert_called_with(player1, -1)

        # Normal params
        # Normal game_id
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1)

        self.assertEqual(result.room_id, "1")
        self.lobby.get_game_info.assert_called_with(player1, "1")

        # Normal game_variation
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "H")

        self.assertEqual(result.room_id, "1")
        self.lobby.get_game_info.assert_called_with(player1, "1")

        # Normal game_type
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "H", 10)

        self.assertEqual(result.room_id, "1")
        self.lobby.get_game_info.assert_called_with(player1, "1")

        # Normal room_type
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "H", 40, 0)

        self.assertEqual(result.room_id, "2")
        self.lobby.get_game_info.assert_called_with(player1, "2")

        # Normal max_stake
        result = self.lobby.find_free_room(player1, FindAndJoin.JUST_FIND, 1, "H", 10, 0, 100)

        self.assertEqual(result.room_id, "extra2")
        self.lobby.get_game_info.assert_called_with(player1, "extra2")

    def test_get_room_info(self):
        player1 = self.player1
        player2 = self.player2

        # Create private room
        self.assertNotIn("11" in self.lobby.room_by_id)
        self.lobby._create_room([11, "room_name", "1_H_10_2", [50, 100, 5000, 100000], 6], player1)

        # Get private room info for owner
        self.lobby.get_room_info(player1, "11")

        player1.protocol.room_info.assert_called_once_with(self.lobby.room_by_id["11"].export_public_data())

        # Get private room info for not an owner
        self.lobby.get_room_info(player2, "11")

        player2.protocol.room_info.assert_not_called()

        # Get public room info
        self.lobby.get_room_info(player2, "1")

        player2.protocol.room_info.assert_called_once_with(self.lobby.room_by_id["1"].export_public_data())

    def test_get_game_info(self):
        player1 = self.player1
        player2 = self.player2

        # Create private room
        self.assertNotIn("11" in self.lobby.room_by_id)
        self.lobby._create_room([11, "room_name", "1_H_10_2", [50, 100, 5000, 100000], 6], player1)

        # Get private room game_info for owner
        self.lobby.get_game_info(player1, "11")

        player1.protocol.game_info.assert_called_once_with(self.lobby.room_by_id["11"].export_public_data(), None)

        # Get private room game_info for not an owner
        self.lobby.get_room_info(player2, "11")

        player2.protocol.game_info.assert_called_once_with(None, None)

        # Get public room game_info
        self.lobby.get_room_info(player2, "1")

        player2.protocol.game_info.assert_called_with(self.lobby.room_by_id["1"].export_public_data(), None)

        # Get full game_info without players
        self.lobby.get_room_info(player2, "1", True)

        player2.protocol.game_info.assert_called_with(self.lobby.room_by_id["1"].export_public_data(), [])

        # Get full game_info with players
        self.lobby.join_the_game(player1, "1", place_index=2)  # , money_in_play=1000
        self.lobby.get_room_info(player2, "1", True)

        player_info_list = [None] * 6
        player_info_list[2] = player1.export_public_data()
        player2.protocol.game_info.assert_called_with(self.lobby.room_by_id["1"].export_public_data(), player_info_list)

    def test_get_player_info_in_game(self):
        player1 = self.player1
        player2 = self.player2

        # Wrong room_id
        self.assertNotIn("111", self.lobby.room_by_id)

        self.lobby.get_player_info_in_game(player1, "111", 2)

        player1.protocol.player_info.assert_not_called()

        # No game
        self.assertIn("1", self.lobby.room_by_id)
        self.assertIsNone(self.lobby.room_by_id["1"].game)

        self.lobby.get_player_info_in_game(player1, "1", 2)

        player1.protocol.player_info.assert_called_once_with(2, None)

        # OK
        self.lobby.join_the_game(player1, "1", place_index=2)  # , money_in_play=1000
        self.assertIsNotNone(self.lobby.room_by_id["1"].game)

        self.lobby.get_player_info_in_game(player1, "1", 2)

        player1.protocol.player_info.assert_called_once_with(2, player1.export_public_data())

        # OK
        self.lobby.get_player_info_in_game(player2, "1", 2)

        player2.protocol.player_info.assert_called_once_with(2, player1.export_public_data())

        # Empty place
        self.lobby.get_player_info_in_game(player2, "1", 3)

        player2.protocol.player_info.assert_called_once_with(3, None)

    def test_join_the_room(self):
        player1 = self.player1
        player2 = self.player2

        self.lobby.add_player(player1)
        self.lobby.add_player(player2)
        self.lobby.house.try_save_house_state_on_change = Mock()

        # OK
        self.assertIsNone(player1.room)
        self.assertIn(player1, self.lobby.present_player_set)

        self.lobby.join_the_room(player1, "1", "not_needed_pwd")

        self.assertEqual(player1.room.room_id, "1")
        self.assertNotIn(player1, self.lobby.present_player_set)
        player1.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["1"].room_model.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_called_once()

        # Wrong room_id
        player1.protocol.reset_mock()
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        self.assertNotIn("111", self.lobby.room_by_id)

        self.lobby.join_the_room(player1, "111")

        player1.protocol.confirm_joined_the_room.assert_not_called()
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

        # OK - to another room
        player1.protocol.reset_mock()
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        self.lobby.room_by_id["2"].room_model.room_password = "xxx"
        self.assertIn("123", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertNotIn("123", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))
        self.assertNotIn(player1, self.lobby.present_player_set)

        self.lobby.join_the_room(player1, "2", "xxx")

        self.assertNotIn("123", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertIn("123", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))
        self.assertNotIn(player1, self.lobby.present_player_set)
        self.assertEqual(player1.room.room_id, "2")
        player1.protocol.confirm_left_the_room.assert_called_once()
        player1.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["2"].room_model.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_called_once()

        # Wrong password
        self.lobby.house.try_save_house_state_on_change.reset_mock()

        self.lobby.join_the_room(player2, "2", "YYY")

        self.assertNotIn("456", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))
        self.assertIn(player2, self.lobby.present_player_set)
        player2.protocol.confirm_joined_the_room.assert_not_called()
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

        # Restoring player in room
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        self.assertIsNone(player2.room)

        player2.room_id = "1"
        self.lobby.join_the_room(player2)

        self.assertIn("456", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertNotIn(player2, self.lobby.present_player_set)
        player2.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["1"].room_model.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

    def test_join_the_game(self):
        player1 = self.player1
        self.user2.money_amount = 16500
        player2 = self.player2
        player3 = self.player3
        player3.money_in_play = 3500

        self.lobby.add_player(player1)
        self.lobby.add_player(player2)
        self.lobby.join_the_room(player1, "1")
        self.lobby.house.try_save_house_state_on_change = Mock()

        # OK
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)

        self.lobby.join_the_game(player1, "1", "not_needed_pwd", 2, 1000)

        self.assertEqual(player1.room.room_id, "1")
        self.assertIsNotNone(player1.game)
        self.assertEqual(player1.place_index, 2)
        self.assertEqual(player1.money_in_play, 1000)
        self.assertEqual(player1.money_amount, 19000)
        player1.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["1"].room_model.export_public_data())
        player1.protocol.player_joined_the_game.assert_called_once_with(2, player1.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_called()
        self.assertEqual(self.lobby.house.try_save_house_state_on_change.call_count, 2)

        # OK
        player2.protocol.reset_mock()
        self.assertIsNotNone(player2.room)
        self.assertIsNone(player2.game)
        self.lobby.room_by_id["1"].room_model.room_password = "xxx"

        self.lobby.join_the_game(player2, "1", "xxx", 2, 2000)

        self.assertEqual(player2.room.room_id, "1")
        self.assertIsNotNone(player2.game)
        self.assertEqual(player2.place_index, 3)
        self.assertEqual(player2.money_in_play, 2000)
        self.assertEqual(player2.money_amount, 14500)
        player1.protocol.confirm_joined_the_room.assert_not_called()
        player1.protocol.player_joined_the_game.assert_called_once_with(3, player2.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_called_once()

        # Wrong room_id
        player1.protocol.reset_mock()
        self.assertNotIn("111", self.lobby.room_by_id)

        self.lobby.join_the_game(player1, "111")  # , money_in_play=1000

        player1.protocol.confirm_joined_the_room.assert_not_called()

        # OK - to another room
        player1.protocol.reset_mock()
        self.lobby.room_by_id["2"].room_model.room_password = "xxx"
        self.assertIn("123", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertNotIn("123", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))

        self.lobby.join_the_game(player1, "2", "xxx")  # , money_in_play=1000

        self.assertNotIn("123", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertIn("123", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))
        self.assertEqual(player1.room.room_id, "2")
        player1.protocol.confirm_left_the_room.assert_called_once()
        player1.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["2"].room_model.export_public_data())
        player1.protocol.player_joined_the_game.assert_called_once_with(0, player1.export_public_data())

        # Wrong password
        player2.protocol.reset_mock()

        self.lobby.join_the_game(player2, "2", "YYY")  # , money_in_play=1000

        self.assertNotIn("456", set(self.lobby.room_by_id["2"].player_by_user_id.keys()))
        self.assertIn(player2, self.lobby.present_player_set)
        player2.protocol.confirm_joined_the_room.assert_not_called()

        # Restoring player in room
        self.assertIsNone(player3.room)
        self.assertIsNone(player3.game)
        self.assertIn(player3, self.lobby.present_player_set)
        self.assertEqual(player3.money_amount, 14500)

        player3.room_id = "1"
        # (Earlier: player3.money_in_play = 3500)
        player3.place_index = 4
        self.lobby.join_the_game(player3)  # , money_in_play=1000

        self.assertIn("456", set(self.lobby.room_by_id["1"].player_by_user_id.keys()))
        self.assertNotIn(player3, self.lobby.present_player_set)
        self.assertIsNotNone(player3.room)
        self.assertIsNotNone(player3.game)
        self.assertEqual(player3.money_in_play, 3500)
        # (money_amount should not be changed on restoring!)
        self.assertEqual(player3.money_amount, 14500)
        self.assertEqual(player2.money_amount, 14500)
        self.assertEqual(player3.game.player_by_place_index_list[4], player3)
        player3.protocol.confirm_joined_the_room.assert_called_once_with(
            self.lobby.room_by_id["1"].room_model.export_public_data())
        player3.protocol.player_joined_the_game.assert_called_once_with(0, player3.export_public_data())

    def test_leave_the_game(self):
        player1 = self.player1
        player2 = self.player2

        self.lobby.add_player(player1)
        self.lobby.add_player(player2)
        self.lobby.join_the_game(player1, "1", money_in_play=1000)
        self.lobby.join_the_room(player2, "1")
        self.lobby.house.try_save_house_state_on_change = Mock()

        # OK
        self.assertTrue(player1.is_connected)
        self.assertIsNotNone(player1.room)
        self.assertIsNotNone(player1.game)
        self.assertEqual(player1.room.room_id, "1")
        self.assertEqual(player1.place_index, 0)
        self.assertEqual(player1.money_in_play, 1000)
        self.assertEqual(player1.money_amount, 19000)

        self.lobby.leave_the_game(player1, "1")

        self.assertEqual(player1.room.room_id, "1")
        self.assertIsNone(player1.game)
        self.assertEqual(player1.place_index, -1)
        self.assertEqual(player1.money_in_play, 0)
        self.assertEqual(player1.money_amount, 20000)
        player1.protocol.player_left_the_game.assert_called_once_with(0)
        self.lobby.house.try_save_house_state_on_change.assert_called()
        self.assertEqual(self.lobby.house.try_save_house_state_on_change.call_count, 2)

        # Again
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        player1.protocol.reset_mock()
        self.assertIsNone(player1.game)

        self.lobby.leave_the_game(player1)

        self.assertIsNone(player1.game)
        self.assertEqual(player1.room.room_id, "1")
        self.assertFalse(player1.protocol.called)
        player1.protocol.player_left_the_game.assert_not_called()
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

        # Not in the game - just in room
        self.assertFalse(player2.is_connected)
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        player2.protocol.reset_mock()
        self.assertEqual(player2.room.room_id, "1")
        self.assertIsNone(player2.game)

        self.lobby.leave_the_game(player2)

        self.assertEqual(player2.room.room_id, "1")
        self.assertIsNone(player2.game)
        self.assertFalse(player2.protocol.called)
        player2.protocol.player_left_the_game.assert_not_called()
        # (As player2 is not connected, there should be no save)
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

    def test_leave_the_room(self):
        player1 = self.player1
        player2 = self.player2

        self.lobby.add_player(player1)
        self.lobby.add_player(player2)
        self.lobby.join_the_game(player1, "1", money_in_play=1000)
        self.lobby.join_the_room(player2, "1")
        self.lobby.house.try_save_house_state_on_change = Mock()

        # OK
        self.assertIsNotNone(player1.room)
        self.assertIsNotNone(player1.game)
        self.assertEqual(player1.room.room_id, "1", 3)
        self.assertEqual(player1.place_index, 3)
        self.assertEqual(player1.money_in_play, 1000)
        self.assertEqual(player1.money_amount, 19000)
        self.assertNotIn(player1, self.lobby.present_player_set)

        self.lobby.leave_the_room(player1)

        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertEqual(player1.place_index, -1)
        self.assertEqual(player1.money_in_play, 0)
        self.assertEqual(player1.money_amount, 20000)
        self.assertIn(player1, self.lobby.present_player_set)
        player1.protocol.player_left_the_game.assert_called_once_with(3)
        player1.protocol.player_left_the_room.assert_called_once_with(player1.export_public_data())
        self.lobby.house.try_save_house_state_on_change.assert_called()
        self.assertEqual(self.lobby.house.try_save_house_state_on_change.call_count, 2)

        # Again
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        player1.protocol.reset_mock()
        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)

        self.lobby.leave_the_room(player1, "1")

        self.assertIsNone(player1.room)
        self.assertIsNone(player1.game)
        self.assertFalse(player1.protocol.called)
        player1.protocol.player_left_the_game.assert_not_called()
        player1.protocol.player_left_the_room.assert_not_called()
        self.lobby.house.try_save_house_state_on_change.assert_not_called()

        # Not in the game - just in room
        self.lobby.house.try_save_house_state_on_change.reset_mock()
        player2.protocol.reset_mock()
        self.assertEqual(player2.room.room_id, "1")
        self.assertIsNone(player2.game)

        self.lobby.leave_the_room(player2)

        self.assertIsNone(player2.room)
        self.assertIsNone(player2.game)
        self.assertFalse(player2.protocol.called)
        player2.protocol.player_left_the_game.assert_not_called()
        player2.protocol.player_left_the_room.assert_called_once_with(player1.export_public_data())
        # (As player2 is not connected, there should be no save)
        self.lobby.house.try_save_house_state_on_change.assert_not_called()


class TestLobby(TestCase, TestRoomManager):
    house_config = None
    lobby = None

    def setUp(self):
        TestRoomManager.setUp(self)

        self.house_config = HouseConfig(house_id="0", data_dir_path="initial_configs/")
        lobby_model = self.house_config.house_model.lobby_model_by_id["1"]
        self.lobby = Lobby(self.house_config, lobby_model)

        self.user1 = utils.create_user(self.house_config, "123", 20000)
        self.player1 = utils.create_player(self.user1)  # Connected, not added to lobby
        self.user2 = utils.create_user(self.house_config, "456", 20000)
        self.player2 = utils.create_player(self.user2, False)  # Not connected, not added
        self.player3 = utils.create_player(self.user2, True)  # Connected, not added

    def test_model_data(self):
        # Getter
        data = self.lobby.model_data

        self.assertEqual(data, self.lobby.lobby_model.export_data())
        self.assertEqual(data[1], "Lobby 1")

        # Setter
        self.assertEqual(self.lobby.lobby_model.lobby_name, "Lobby 1")

        data[1] = "some new Name"
        self.lobby.model_data = data

        self.assertEqual(self.lobby.lobby_model.lobby_name, "some new Name")

        # Set None - no changes
        self.lobby.model_data = None

        self.assertEqual(self.lobby.lobby_model.lobby_name, "some new Name")

        # Set empty - no changes
        self.lobby.model_data = []

        self.assertEqual(self.lobby.lobby_model.lobby_name, "some new Name")

    def test_constructor(self):
        TestRoomManager.test_constructor(self)

        self.assertIsNotNone(self.lobby.house_config)
        self.assertIsNotNone(self.lobby.house_model)
        self.assertIsNotNone(self.lobby.lobby_model)
        self.assertIsNotNone(self.lobby.logging)
        self.assertEqual(self.lobby.player_set, set())
        self.assertEqual(self.lobby.present_player_set, set())

    def test_dispose(self):
        TestRoomManager.test_dispose(self)

        self.lobby.player_set.add(Mock())
        self.lobby.present_player_set.add(Mock())

        self.lobby.dispose()

        self.assertIsNone(self.lobby.house_config)
        self.assertIsNone(self.lobby.house_model)
        self.assertIsNone(self.lobby.lobby_model)
        self.assertIsNone(self.lobby.logging)
        self.assertEqual(self.lobby.player_set, set())
        self.assertEqual(self.lobby.present_player_set, set())

    def test_add_player(self):
        # OK. Remove from previous lobby
        another_lobby = Lobby(Mock(), Mock())
        player = utils.create_player(self.user1, True)
        another_lobby.add_player(player)
        self.assertEqual(player.lobby, another_lobby)
        self.assertIn(player, another_lobby.player_set)
        self.assertNotIn(player, self.lobby.player_set)

        self.lobby.add_player(player)

        self.assertEqual(player.lobby, self.lobby)
        self.assertNotIn(player, another_lobby.player_set)
        self.assertIn(player, self.lobby.player_set)

        # OK
        # self.lobby.remove_player(self.player1)
        # self.player1.protocol.reset_mock()
        self.assertEqual(len(self.lobby.player_set), 1)

        self.lobby.add_player(self.player1)

        self.assertEqual(len(self.lobby.player_set), 2)
        self.player1.protocol.method_calls = [
            call.goto_lobby(self.lobby.lobby_model.export_public_data())
        ]

        # Again
        self.player1.protocol.reset_mock()
        self.assertEqual(len(self.lobby.player_set), 2)

        self.lobby.add_player(self.player1)

        self.assertEqual(len(self.lobby.player_set), 2)
        self.player1.protocol.method_calls = [
            call.goto_lobby(self.lobby.lobby_model.export_public_data())
        ]

        # OK. Restoring
        self.player2.room_id = 1
        self.lobby.add_player(self.player2)

        player_info_list = [None] * 6
        self.player2.protocol.method_calls = [
            call.goto_lobby(self.lobby.lobby_model.export_public_data()),
            call.confirm_joined_the_room(self.lobby.room_by_id["1"].room_model.export_public_data()),
            call.game_info(self.lobby.room_by_id["1"].game.export_public_data(), player_info_list)
        ]

        # OK. Restoring in game
        self.assertIsNone(self.player3.lobby)
        self.assertIsNone(self.player3.room)
        self.assertIsNone(self.player3.game)

        self.player3.room_id = 1
        self.player3.place_index = 0
        self.lobby.add_player(self.player3)

        self.assertIsNotNone(self.player3.lobby)
        self.assertIsNotNone(self.player3.room)
        self.assertIsNotNone(self.player3.game)
        player_info_list = [None] * 6
        player_info_list[0] = self.player3.export_public_data()
        self.player3.protocol.method_calls = [
            call.goto_lobby(self.lobby.lobby_model.export_public_data()),
            call.confirm_joined_the_room(self.lobby.room_by_id["1"].room_model.export_public_data()),
            call.player_joined_the_game(0, self.player3.export_public_data()),
            call.log("Some Name456 joined the play"),
            call.game_info(self.lobby.room_by_id["1"].game.export_public_data(), player_info_list)
        ]

    def test_remove_player(self):
        self.lobby.leave_the_room = Mock()

        # OK
        self.assertIsNotNone(self.player1.lobby)
        self.assertIn(self.player1, self.lobby.player_set)
        self.assertIn(self.player1, self.lobby.present_player_set)

        self.lobby.remove_player(self.player1)

        self.assertIsNone(self.player1.lobby)
        self.assertNotIn(self.player1, self.lobby.player_set)
        self.assertNotIn(self.player1, self.lobby.present_player_set)
        self.lobby.leave_the_room.assert_called_once_with(self.player1)

        # Again
        self.lobby.leave_the_room.reset_mock()
        self.assertIsNone(self.player1.lobby)
        self.assertNotIn(self.player1, self.lobby.player_set)
        self.assertNotIn(self.player1, self.lobby.present_player_set)

        self.lobby.remove_player(self.player1)

        self.assertIsNone(self.player1.lobby)
        self.assertNotIn(self.player1, self.lobby.player_set)
        self.assertNotIn(self.player1, self.lobby.present_player_set)
        self.lobby.leave_the_room.assert_not_called()

    def test_send_message(self):
        self.lobby.add_player(self.player1)
        self.lobby.add_player(self.player2)
        self.lobby.add_player(self.player3)
        self.lobby.join_the_room(self.player3)
        self.assertEqual(len(self.lobby.player_set), 3)
        self.assertEqual(len(self.lobby.present_player_set), 2)

        TestRoomSendMixIn.do_test_send_message(self, self.lobby, self.lobby.present_player_set, self.player1)

        # Ensure only present_player_set were notified
        for player in self.lobby.player_set:
            if player not in self.lobby.present_player_set:
                player.protocol.send_message.assert_not_called()

    def test_send_message_without_receiver(self):
        self.lobby.add_player(self.player1)
        self.lobby.add_player(self.player2)
        self.lobby.add_player(self.player3)
        self.lobby.join_the_room(self.player3)
        self.assertEqual(len(self.lobby.player_set), 3)
        self.assertEqual(len(self.lobby.present_player_set), 2)

        TestRoomSendMixIn.do_test_send_message_without_receiver(self, self.lobby, self.lobby.present_player_set, self.player1)

        # Ensure only present_player_set were notified
        for player in self.lobby.player_set:
            if player not in self.lobby.present_player_set:
                player.protocol.send_message.assert_not_called()
