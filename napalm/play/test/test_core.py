from unittest import TestCase
from unittest.mock import Mock

from napalm.play.core import HouseConfig
from napalm.play.game import GameConfigModel
from napalm.play.house import HouseModel
from napalm.play.lobby import LobbyModel, RoomModel


# Stubs

class MyGameConfigModel(GameConfigModel):
    param1 = None
    param2 = None
    param3 = None

    @property
    def _config_property_names(self):
        return ["param1", "param2", "param3"]


class MyRoomModel(RoomModel):
    pass


class MyLobbyModel(LobbyModel):
    pass


class MyHouseModel(HouseModel):
    pass


# Test

class TestHouseConfigAndModels(TestCase):
    house_config = None

    def setUp(self):
        super().setUp()
        self.house_config = HouseConfig(house_id=1, data_dir_path="initial_configs/",
                                        game_config_model_class=MyGameConfigModel,
                                        room_model_class=MyRoomModel,
                                        lobby_model_class=MyLobbyModel,
                                        house_model_class=MyHouseModel)

    def tearDown(self):
        self.house_config.dispose()
        super().tearDown()

    # Utility

    def reload(self):
        self.house_config._data_dir_path = "changed_configs/"
        self.house_config.reload()

    def assert_model_matches(self, model, expected_dict):
        for key, value in expected_dict.items():
            # (For RoomModel)
            if key == "game_params":
                self.assert_model_matches(model, value)
            else:
                self.assertEqual(getattr(model, key), value, str(model.id) + "|" + str(key))

    def assert_model_does_not_match(self, model, expected_dict):
        for key, value in expected_dict.items():
            if getattr(model, key) != value:
                return
        self.fail("Model matches dict")

    def assert_house_model_reloaded(self, house_model, expected_prev_dict, expected_dict):
        self.assert_model_matches(house_model, expected_dict)

        prev_lobbies = expected_prev_dict["lobbies"]
        new_lobbies = expected_dict["lobbies"]
        new_lobbies = new_lobbies.values() if isinstance(new_lobbies, dict) else new_lobbies
        # Items from lobby_model_list are not removed, but only marked for delete
        self.assertGreaterEqual(len(house_model.lobby_model_list), len(prev_lobbies))

        # Assert lobbies marked deleting properly
        for lobby_model in house_model.lobby_model_list:
            # Model is copy
            self.assertIsNotNone(lobby_model.parent_model)
            if lobby_model.id in new_lobbies:
                # Not deleting
                self.assertFalse(lobby_model.is_marked_for_delete)
            else:
                # Deleting
                self.assertTrue(lobby_model.is_marked_for_delete)

    # Tests

    def test_dispose_models(self):
        # Ensure
        self.assertNotEqual(GameConfigModel.model_list, [])
        self.assertNotEqual(RoomModel.model_list, [])
        self.assertNotEqual(LobbyModel.model_list, [])
        self.assertNotEqual(HouseModel.model_list, [])
        self.assertNotEqual(GameConfigModel.model_by_id, {})
        self.assertNotEqual(RoomModel.model_by_id, {})
        self.assertNotEqual(LobbyModel.model_by_id, {})
        self.assertNotEqual(HouseModel.model_by_id, {})

        # Dispose
        HouseConfig.dispose_models()

        # Assert
        # self.assertIsNone(self.house_config.logging)
        self.assertIsNone(GameConfigModel.model_list)
        self.assertIsNone(RoomModel.model_list)
        self.assertIsNone(LobbyModel.model_list)
        self.assertIsNone(HouseModel.model_list)
        self.assertIsNone(GameConfigModel.model_by_id)
        self.assertIsNone(RoomModel.model_by_id)
        self.assertIsNone(LobbyModel.model_by_id)
        self.assertIsNone(HouseModel.model_by_id)

    def test_dispose(self):
        house_model = self.house_config.house_model
        house_model.dispose = Mock(side_effect=house_model.dispose)
        HouseConfig.dispose_models = Mock(side_effect=HouseConfig.dispose_models)

        # Ensure
        self.assertNotEqual(self.house_config._backend_info_by_backend, {})
        self.assertNotEqual(GameConfigModel.model_list, [])
        # ...
        self.assertNotEqual(HouseModel.model_by_id, {})

        # Dispose
        self.house_config.dispose()

        # Assert
        # self.assertIsNone(self.house_config.logging)
        self.assertIsNone(self.house_config.house_model)
        house_model.dispose.assert_called()
        HouseConfig.dispose_models.assert_called_once()

        self.assertEqual(self.house_config._backend_info_by_backend, {})
        self.assertIsNone(GameConfigModel.model_list)
        # ...
        self.assertIsNone(HouseModel.model_by_id)

    def test_house_models(self):
        self.assertFalse(HouseModel.is_change_on_command)

        # house_config.house_model
        self.assertEqual(self.house_config.house_id, "1")

        expected1 = {
            "house_id": "1",
            "house_name": "server1",
            "host": "localhost",
            "port": 41001,
            "lobbies": ["1", "2"]
        }
        house_model1 = HouseModel.get_model_by_id(1)
        self.assertIsInstance(house_model1, MyHouseModel)
        self.assertIs(house_model1, self.house_config.house_model)
        self.assert_model_matches(house_model1, expected1)
        self.assertEqual(len(house_model1.lobby_model_list), 2)

        with self.assertRaises(Exception):
            self.assertEqual(house_model1.some_unknown, None)

        # All other house models
        self.assertEqual(len(HouseModel.model_by_id), 3)

        expected2 = {
            "house_id": "2",
            "house_name": "server2",
            "host": "localhost",
            "port": 41002,
            "lobbies": ["2"]
        }
        house_model2 = HouseModel.get_model_by_id(2)
        self.assert_model_matches(house_model2, expected2)
        self.assertEqual(len(house_model2.lobby_model_list), 1)

        expected3 = {
            "house_id": "3",
            "house_name": "server3",
            "host": "localhost",
            "port": 41003,
            "lobbies": ["3"]
        }
        house_model3 = HouseModel.get_model_by_id("3")
        self.assert_model_matches(house_model3, expected3)
        self.assertEqual(len(house_model3.lobby_model_list), 0)

        # RELOAD
        self.reload()

        # ???
        # Global models never marked deleting
        for lobby_model in LobbyModel.model_by_id.values():
            self.assertFalse(lobby_model.is_marked_for_delete, lobby_model.id)
        # Not removing, but only marked for deleting (stay the same)
        self.assertEqual(len(HouseModel.model_by_id), 3)

        # house_config.house_model
        self.assertEqual(self.house_config.house_id, "1")
        self.assertIs(house_model1, self.house_config.house_model)

        expected1_changed = {
            "house_id": "1",
            "house_name": "server001",
            "host": "mytest.localhost",
            "port": 41501,
            "lobbies": ["3"]
        }
        # Not deleting
        self.assertFalse(house_model1.is_marked_for_delete)
        # (Changed)
        self.assert_house_model_reloaded(house_model1, expected1, expected1_changed)
        self.assertEqual(len(house_model1.lobby_model_list), 3)

        # All other house models

        expected2_changed = {
            "house_id": "2",
            "house_name": "server2",
            "host": "localhost",
            "port": 41002,
            "lobbies": ["2"]
        }
        # Deleting
        self.assertTrue(house_model2.is_marked_for_delete)
        # (Not changed)
        self.assert_house_model_reloaded(house_model2, expected2, expected2_changed)
        self.assertEqual(len(house_model2.lobby_model_list), 1)

        expected3_changed = {
            "house_id": "3",
            "house_name": "server003",
            "host": "localhost3",
            "port": 41503,
            "lobbies": {
                "11": "2",
                "22": "3"
            }
        }
        # Not deleting
        self.assertFalse(house_model3.is_marked_for_delete)
        # (Changed)
        self.assert_house_model_reloaded(house_model3, expected3, expected3_changed)
        self.assertEqual(len(house_model3.lobby_model_list), 2)

    def test_lobby_models(self):
        self.assertFalse(LobbyModel.is_change_on_command)

        # Get
        house_model = self.house_config.house_model
        lobby_submodel1 = house_model.lobby_model_by_id["1"]
        lobby_submodel2 = house_model.lobby_model_by_id["2"]
        # lobby_submodel3 = house_model.lobby_model_by_id["3"]
        lobby_model1 = LobbyModel.get_model_by_id(1)
        lobby_model2 = LobbyModel.get_model_by_id("2")
        # lobby_model3 = LobbyModel.get_model_by_id(3)

        # Ensure models are derived
        lobby_submodels = [lobby_submodel1, lobby_submodel2]
        lobby_models = [lobby_model1, lobby_model2]
        for i in range(len(lobby_models)):
            lobby_model = lobby_models[i]
            lobby_submodel = lobby_submodels[i]
            self.assertIsNot(lobby_submodel, lobby_model)
            self.assertIs(lobby_submodel.parent_model, lobby_model)
            self.assertIn(lobby_submodel, lobby_model.derived_models)

        # Asserts
        expected1 = {
            "lobby_id": "1",
            "lobby_name": "Lobby 1"
        }
        expected2 = {
            "lobby_id": "2",
            "lobby_name": "Lobby 2"
        }
        # expected3 = {
        #     "lobby_id": "3",
        #     "lobby_name": ""
        # }
        expected_list = [expected1, expected2]
        room_count_list = [3, 3]
        for i in range(len(lobby_models)):
            model = lobby_models[i]
            submodel = lobby_submodels[i]
            expected = expected_list[i]

            self.assertIsInstance(model, MyLobbyModel)
            self.assertIsInstance(submodel, MyLobbyModel)
            self.assert_model_matches(model, expected)
            self.assert_model_matches(submodel, expected)
            self.assertEqual(len(model.room_model_list), room_count_list[i])
            self.assertEqual(len(model.available_room_models), room_count_list[i])

        # RELOAD
        self.reload()

        # Asserts
        expected1_changed = {
            "lobby_id": "1",
            "lobby_name": "Lobby 1 changed"
        }
        expected2_changed = {
            "lobby_id": "2",
            "lobby_name": "Lobby 2 changed"
        }
        expected3_changed = {
            "lobby_id": "3",
            "lobby_name": "Lobby 3 changed"
        }
        expected_changed_list = [expected1_changed, expected2_changed, expected3_changed]
        room_count_changed_list = [5, 4, 3]
        available_room_count_changed_list = [4, 4, 3]
        for i in range(len(lobby_models)):
            model = lobby_models[i]
            submodel = lobby_submodels[i]
            expected = expected_list[i]
            expected_changed = expected_changed_list[i]

            # (LobbyModel.is_change_on_command=False, so no need in apply_changes())
            # self.assert_model_matches(submodel, expected)
            # self.assert_model_matches(model, expected)
            # self.assertEqual(len(model.room_model_list), room_count_list[i], model.lobby_id)
            # # +self.assertEqual(len(model.available_room_models), room_count_list[i], model.lobby_id)
            #
            # submodel.apply_changes()

            self.assert_model_matches(submodel, expected_changed)
            # self.assert_model_matches(model, expected)
            self.assert_model_matches(model, expected_changed)
            self.assertEqual(len(model.room_model_list), room_count_changed_list[i], model.lobby_id)
            self.assertEqual(len(model.available_room_models), available_room_count_changed_list[i], model.lobby_id)

    def test_room_models(self):
        self.assertTrue(RoomModel.is_change_on_command)

        # Get
        # house_model = self.house_config.house_model
        lobby_model1 = LobbyModel.get_model_by_id(1)
        # lobby_model2 = LobbyModel.get_model_by_id("2")
        # lobby_model3 = LobbyModel.get_model_by_id(3)
        # lobby_submodel1 = house_model.lobby_model_by_id["1"]
        # lobby_submodel2 = house_model.lobby_model_by_id["2"]
        # lobby_submodel3 = house_model.lobby_model_by_id["3"]

        room_model_1 = RoomModel.get_model_by_id("1")
        room_model_2 = RoomModel.get_model_by_id("2")
        room_model_3 = RoomModel.get_model_by_id("3")
        room1_submodel_1 = lobby_model1.room_model_by_id["1"]
        room1_submodel_2 = lobby_model1.room_model_by_id["2"]
        room1_submodel_3 = lobby_model1.room_model_by_id["3"]

        # room1_submodel1 = lobby_model1.room_model_by_id["1"]
        # room1_submodel2 = lobby_model1.room_model_by_id["2"]
        # room1_submodel4 = lobby_model1.room_model_by_id["4"]

        # Ensure models are derived
        room_submodels = [room1_submodel_1, room1_submodel_2, room1_submodel_3]
        room_models = [room_model_1, room_model_2, room_model_3]
        for i in range(len(room_submodels)):
            model = room_models[i]
            submodel = room_submodels[i]
            self.assertIsNone(model)
            # self.assertIsInstance(model, MyRoomModel)
            self.assertIsInstance(submodel, MyRoomModel)
            # self.assertIsNot(submodel, model)
            # self.assertIs(submodel.parent_model, model)
            # self.assertIn(submodel, model.derived_models)

        # Asserts
        expected_25_50 = {
            "room_id": None,
            "room_name": "001_room 25/50",
            "room_code": "1_H_10_0",
            "game_params": {
                "min_stake": 25,
                "max_stake": 50,
                # (not considered in RoomModel)
                # "min_buy_in": 500,
                # "max_buy_in": 10000,
                # "pot_limit_type": None,
                # "average_pot": None,
                # "players_per_flop_percents": None
            },
            "max_player_count": 9,
            "max_visitor_count": -1,
            "room_password": "",
            "turn_timeout_sec": 10
        }
        expected_50_100 = expected_25_50.copy()
        expected_50_100.update(room_name="001_room 50/100", max_player_count=6)
        expected_50_100["game_params"] = {
            "min_stake": 50,
            "max_stake": 100,
            # (not considered in RoomModel)
            # "min_buy_in": 1000,
            # "max_buy_in": 20000,
            # "pot_limit_type": None,
            # "average_pot": None,
            # "players_per_flop_percents": None
        }
        # expected_1 = expected_25_50.copy()
        # expected_1.update(room_id="1")
        # expected_2 = expected_50_100.copy()
        # expected_2.update(room_id="2")
        expected_lobby1_room1 = expected_25_50.copy()
        expected_lobby1_room1.update(room_id="1", room_name="1_room1", room_code="1_H_40_0")
        expected_lobby1_room2 = expected_50_100.copy()
        expected_lobby1_room2.update(room_id="2", room_name="1_room2", room_code="2_B_10_0", max_player_count=6)
        expected_lobby1_room3 = expected_50_100.copy()
        expected_lobby1_room3.update(room_id="3", room_name="1_room3", room_code="1_H_40_0", tournament_type=1)
        # Updating during reloading
        # expected_lobby1_room3_ = expected_25_50.copy()
        # expected_lobby1_room3_.update(room_id="3", room_name="1_room3")

        # expected_list = [expected_1, expected_2]
        # for i in range(len(room_models)):
        #     submodel = room_submodels[i]
        #     model = room_models[i]
        #     expected = expected_list[i]
        #
        #     self.assert_model_matches(submodel, expected)
        #     self.assert_model_matches(model, expected)
        expected_list = [expected_lobby1_room1, expected_lobby1_room2, expected_lobby1_room3]
        for i in range(len(room_submodels)):
            submodel = room_submodels[i]
            expected = expected_list[i]

            self.assert_model_matches(submodel, expected)
        # self.assert_model_does_not_match(room1_submodel_3, expected_lobby1_room3_)
        #
        # room1_submodel_3.apply_changes()
        # self.assert_model_does_not_match(room1_submodel_3, expected_lobby1_room3)
        # self.assert_model_matches(room1_submodel_3, expected_lobby1_room3_)

        # RELOAD
        self.reload()

        # Asserts
        expected_25_50["room_name"] = "1_room0001"
        expected_50_100["room_name"] = "1_room0002"
        # expected_1_changed = expected_50_100.copy()
        # expected_1_changed.update(room_id="1")
        # expected_2_changed = expected_25_50.copy()
        # expected_2_changed.update(room_id="2")
        expected_lobby1_room1 = expected_25_50.copy()
        expected_lobby1_room1.update(room_id="1")
        expected_lobby1_room2 = expected_25_50.copy()
        expected_lobby1_room2.update(room_id="2", room_name="1_room002", room_code="1_H_40_0", max_player_count=6)
        # (not changed - deleted)
        # expected_lobby1_room3 = expected_50_100.copy()
        # expected_lobby1_room3.update(room_id="3", room_name="1_room3", room_code="1_H_40_0", tournament_type=1)
        # expected_lobby1_room4_changed = expected_lobby1_room4

        expected_changed_list = [expected_lobby1_room1, expected_lobby1_room2, expected_lobby1_room3]
        for i in range(len(room_submodels)):
            # model = room_models[i]
            submodel = room_submodels[i]
            expected = expected_list[i]
            expected_changed = expected_changed_list[i]

            # (LobbyModel.is_change_on_command=True, so model would be updated only after apply_changes())
            self.assert_model_matches(submodel, expected)

            submodel.apply_changes()

            # self.assert_model_matches(model, expected)
            self.assert_model_matches(submodel, expected_changed)

            # Note: we don't have to apply_changes on global model because it already was made on reload
            # self.assert_model_matches(model, expected_changed)

    def test_game_config_models(self):
        self.assertTrue(GameConfigModel.is_change_on_command)

        game_config_models = [MyGameConfigModel.get_model_by_id("H"),
                              MyGameConfigModel.get_model_by_id("OH")]
        game_config_submodels = [MyGameConfigModel.get_model_copy_by_id("H"),
                                 MyGameConfigModel.get_model_copy_by_id("OH")]
        # expected_list = [{
        #     "param1": "value1",
        #     "param2": "value2",
        #     "param3": "value3"
        # }, {
        #     "param1": "value3",
        #     "param2": "value4",
        #     "param3": None
        # }]
        expected_list = [{
            "param1": None,
            "param2": None,
            "param3": "valueH3"
        }, {
            "param1": "valueOH1",
            "param2": None,
            "param3": None
        }]
        for i in range(len(game_config_models)):
            model = game_config_models[i]
            submodel = game_config_submodels[i]
            expected = expected_list[i]

            self.assertIsInstance(model, MyGameConfigModel)
            self.assertIsInstance(submodel, MyGameConfigModel)
            self.assert_model_matches(submodel, expected)
            self.assert_model_matches(model, expected)

        # RELOAD
        self.reload()

        # expected_changed_list = [{
        #     "param1": "value001",
        #     "param2": "value002",
        #     "param3": "value3"
        # }, {
        #     "param1": "value003",
        #     "param2": "value004",
        #     "param3": "value005"
        # }]
        expected_changed_list = [{
            "param1": None,
            "param2": None,
            "param3": "value__H3"
        }, {
            "param1": "value__OH1",
            "param2": None,
            "param3": None
        }]
        for i in range(len(game_config_models)):
            model = game_config_models[i]
            submodel = game_config_submodels[i]
            expected = expected_list[i]
            expected_changed = expected_changed_list[i]

            self.assertNotEqual(expected_changed, expected)

            self.assert_model_matches(model, expected_changed)
            self.assert_model_matches(submodel, expected)

            submodel.apply_changes()

            self.assert_model_matches(model, expected_changed)
            self.assert_model_matches(submodel, expected_changed)
