import time
from unittest import TestCase
from unittest.mock import Mock, patch, MagicMock, call

from napalm.async import ThreadedTimer, TwistedTimer
from napalm.core import SocketApplication, SocketGameApplication, ConfigurableMixIn, ExportableMixIn, BaseModel, \
    ReloadableModel, ReloadableMultiModel
from napalm.socket.server import TwistedTCPServer, ServerConfig, AbstractServer


# Application

class MyTwistedTCPServer(TwistedTCPServer):
    pass


class MyTCPServer(AbstractServer):
    def start(self):
        pass


class House:
    def __init__(self, config):
        pass


class TestSocketApplication(TestCase):
    def test_init(self):
        with self.assertRaises(Exception):
            SocketApplication(None, None)

        # No exceptions for simple config
        config = ServerConfig()
        SocketApplication(config)

        # TwistedTCPServer subclass
        config = ServerConfig()
        app = SocketApplication(config, MyTwistedTCPServer)

        self.assertEqual(app.config, config)
        self.assertEqual(app.config.timer_class, TwistedTimer)
        self.assertIsInstance(app.server, MyTwistedTCPServer)

        # TwistedTCPServer
        app = SocketApplication(config, TwistedTCPServer)

        self.assertEqual(app.config.timer_class, TwistedTimer)
        self.assertIsInstance(app.server, TwistedTCPServer)

        # Any other server
        app = SocketApplication(config, MyTCPServer)

        # self.assertEqual(app.config.timer_class, ThreadedTimer)
        self.assertIsInstance(app.server, MyTCPServer)

        # Default server
        app = SocketApplication(config)

        self.assertIsNotNone(app.server)
        self.assertIsInstance(app.server, AbstractServer)

    def test_start(self):
        app = SocketApplication(ServerConfig(), MyTCPServer)
        app.server.start = Mock()

        app.start()

        app.server.start.assert_called_once()


class TestSocketGameApplication(TestCase):
    def setUp(self):
        super().setUp()

    def test_init(self):
        with self.assertRaises(Exception):
            SocketGameApplication(None, None)

        config = ServerConfig()
        config.house_class = House

        # Normal
        app = SocketGameApplication(config)

        self.assertEqual(app.config, config)
        # self.assertEqual(app.config.timer_class, ThreadedTimer)
        self.assertIsInstance(app.server, AbstractServer)
        self.assertIsInstance(app.house, House)

        # Using Twisted (test super().__init__ called)
        app = SocketGameApplication(config, MyTwistedTCPServer)

        self.assertEqual(app.config.timer_class, TwistedTimer)
        self.assertIsInstance(app.server, MyTwistedTCPServer)

    @patch("napalm.core.SocketApplication.start")
    def test_start(self, super_start_mock):
        config = ServerConfig()
        config.house_class = Mock
        app = SocketGameApplication(config)
        app.house.start = Mock()

        app.start()

        app.house.start.assert_called_once()
        super_start_mock.assert_called_once()

    def test_start_sequence(self):
        mock = MagicMock(spec=SocketGameApplication)
        SocketGameApplication.start(mock)

        self.assertEqual(mock.mock_calls, [call.house.start(), call.server.start()])


# Configurable

class MyConfigurable(ConfigurableMixIn):
    param1 = None
    param2 = None
    param3 = None

    @property
    def _config_property_names(self):
        return ["param1", "param2"]


class TestConfigurableMixIn(TestCase):
    initial_config = {"param1": 1, "param2": "value2", "param3": 3}

    def test_workflow(self):
        # Init
        configurable = MyConfigurable(self.initial_config)

        self.assertEqual(configurable.param1, 1)
        self.assertEqual(configurable.param2, "value2")
        self.assertIsNone(configurable.param3)

        # Reset
        configurable.param1 = 1001
        configurable.param2 = "some"
        # (Ensure)
        self.assertNotEqual(configurable.param1, 1)
        self.assertNotEqual(configurable.param2, "value2")
        self.assertIsNone(configurable.param3)

        configurable.reset()

        self.assertEqual(configurable.param1, 1)
        self.assertEqual(configurable.param2, "value2")
        self.assertIsNone(configurable.param3)

    def test_init(self):
        configurable = MyConfigurable(self.initial_config)

        self.assertEqual(configurable._initial_config, self.initial_config)
        self.assertEqual(configurable.param1, 1)
        self.assertEqual(configurable.param2, "value2")
        self.assertIsNone(configurable.param3)

    @patch("napalm.utils.object_util.set_up_object")
    def test_apply_initial_config(self, set_up_object_mock):
        configurable = MyConfigurable(self.initial_config)
        configurable._apply_initial_config()

        self.assertEqual(set_up_object_mock.call_count, 2)
        set_up_object_mock.assert_called_with(configurable, self.initial_config, configurable._config_property_names)

    def test_reset(self):
        configurable = MyConfigurable(self.initial_config)
        configurable._apply_initial_config = Mock()

        configurable.reset()

        configurable._apply_initial_config.assert_called_once()


# Exportable

class MyExportable(ExportableMixIn):
    param1 = None
    param2 = None
    param3 = None

    # (For test_apply_changes)
    _property_names = ["param1", "param2"]
    _public_property_names = ["param2", "param3"]

    # @property
    # def _property_names(self):
    #     return ["param1", "param2"]
    #
    # @property
    # def _public_property_names(self):
    #     return ["param2", "param3"]


class TestExportableMixIn(TestCase):
    exportable = None

    def setUp(self):
        super().setUp()

        self.exportable = MyExportable()
        self.exportable.param1 = 1
        self.exportable.param2 = 2
        self.exportable.param3 = 3

    def test_property_names(self):
        self.exportable_mixin = ExportableMixIn()

        self.assertEqual(self.exportable_mixin._property_names, [])

    def test_public_property_names(self):
        class CustomExportable(ExportableMixIn):
            @property
            def _property_names(self):
                return ["param_x", "param_y"]

        self.custom_exportable = CustomExportable()

        self.assertEqual(self.custom_exportable._public_property_names, ["param_x", "param_y"])

    def test_export_data(self):
        self.assertEqual(self.exportable.export_data(), [1, 2])

    def test_import_data(self):
        start_time = time.time()
        self.exportable.import_data([5, 6, 7])

        self.assertEqual(self.exportable.param1, 5)
        self.assertEqual(self.exportable.param2, 6)
        self.assertEqual(self.exportable.param3, 3)

        self.exportable.import_data({"param1": 15, "param2": 16, "param3": 17})

        self.assertEqual(self.exportable.param1, 15)
        self.assertEqual(self.exportable.param2, 16)
        self.assertEqual(self.exportable.param3, 3)
        self.assertGreaterEqual(self.exportable.change_time, start_time)
        self.assertLessEqual(self.exportable.change_time, time.time())

    def test_import_data_with_change_on_command(self):
        self.exportable.import_data([5, 6, 7])

        self.assertEqual(self.exportable.param1, 5)
        self.assertEqual(self.exportable.param2, 6)
        self.assertEqual(self.exportable.param3, 3)

        self.exportable.is_change_on_command = True
        # (No changes)
        self.exportable.import_data([5, 6, 7])

        self.assertEqual(self.exportable._changes_queue, [])
        self.assertEqual(self.exportable.param1, 5)
        self.assertEqual(self.exportable.param2, 6)
        self.assertEqual(self.exportable.param3, 3)

        # (With changes)
        self.exportable.import_data({"param1": 15, "param2": 16, "param3": 17})

        self.assertEqual(len(self.exportable._changes_queue), 1)
        self.assertEqual(self.exportable.param1, 5)
        self.assertEqual(self.exportable.param2, 6)
        self.assertEqual(self.exportable.param3, 3)

    def test_export_public_data(self):
        self.assertEqual(self.exportable.export_public_data(), [2, 3])

    def test_import_public_data(self):
        start_time = time.time()

        self.exportable.import_public_data([5, 6, 7])

        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 5)
        self.assertEqual(self.exportable.param3, 6)

        self.exportable.is_change_on_command = True
        # (No changes)
        self.exportable.import_public_data([5, 6, 7])

        self.assertEqual(self.exportable._changes_queue, [])
        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 5)
        self.assertEqual(self.exportable.param3, 6)

        # (With changes)
        self.exportable.import_public_data({"param1": 15, "param2": 16, "param3": 17})

        self.assertEqual(len(self.exportable._changes_queue), 1)
        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 5)
        self.assertEqual(self.exportable.param3, 6)

    def test_import_public_data_with_change_on_command(self):
        start_time = time.time()

        self.exportable.import_public_data([5, 6, 7])

        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 5)
        self.assertEqual(self.exportable.param3, 6)

        self.exportable.import_public_data({"param1": 15, "param2": 16, "param3": 17})

        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 16)
        self.assertEqual(self.exportable.param3, 17)

    def test_apply_changes(self):
        start_time = time.time()
        self.exportable.is_change_on_command = True
        self.exportable.param4 = 4
        self.exportable._property_names = ["param1", "param2"]
        self.exportable._public_property_names = ["param3", "param4"]
        self.assertFalse(self.exportable.is_changed)

        # import_data()
        self.exportable.import_data([5, 6, 7, 8])
        # (Test that property names are also save with data in changes_queue)
        self.exportable._property_names = ["param2"]
        self.exportable.import_data({"param1": 15, "param2": 16, "param3": 17, "param4": 18})
        # import_public_data()
        self.exportable.import_public_data({"param1": 25, "param2": 26, "param3": 27, "param4": 28})
        self.exportable._public_property_names = ["param4"]
        self.exportable.import_public_data({"param1": 35, "param2": 36, "param3": 37, "param4": 38})

        self.assertTrue(self.exportable.is_changed)
        self.assertEqual(self.exportable.param1, 1)
        self.assertEqual(self.exportable.param2, 2)
        self.assertEqual(self.exportable.param3, 3)
        self.assertEqual(self.exportable.param4, 4)
        self.assertIsNone(self.exportable.change_time)

        # apply_changes()
        self.exportable.apply_changes()

        self.assertFalse(self.exportable.is_changed)
        self.assertEqual(self.exportable.param1, 5)
        self.assertEqual(self.exportable.param2, 16)
        self.assertEqual(self.exportable.param3, 27)
        self.assertEqual(self.exportable.param4, 38)
        self.assertGreaterEqual(self.exportable.change_time, start_time)
        self.assertLessEqual(self.exportable.change_time, time.time())


# Model

class TestBaseModel(TestCase):
    def test_inherits(self):
        model = BaseModel(None)

        self.assertIsInstance(model, ConfigurableMixIn)
        self.assertIsInstance(model, ExportableMixIn)

    def test_constructors(self):
        config = {"some": "value"}
        # with patch("napalm.test.test_core.BaseModel", BaseModel) as model_mock:
        #     temp = model_mock._apply_initial_config
        #     model_mock._apply_initial_config = Mock()
        #     model = BaseModel(config)
        #     model_mock._apply_initial_config.assert_called_once()
        #     model_mock._apply_initial_config = temp
        class MyBaseModel(BaseModel):
            _apply_initial_config = Mock()
        model = MyBaseModel(config)
        model._apply_initial_config.assert_called_once()

        self.assertIs(model._initial_config, config)
        self.assertIsNotNone(model._changes_queue)

    def test_default_property_names(self):
        class MyModel(BaseModel):
            @property
            def _config_property_names(self):
                return ["param1", "param10"]

        model = MyModel(None)

        self.assertEqual(model._property_names, ["param1", "param10", "_changes_queue"])
        self.assertEqual(model._public_property_names, ["param1", "param10", "_changes_queue"])


class MyReloadableModel(ReloadableModel):
    id_name = "my_id"

    my_id = None
    param1 = None

    @property
    def _config_property_names(self):
        return ["my_id", "param1"]


class MySubReloadableModel(MyReloadableModel):
    param2 = None
    param3 = None

    @property
    def _config_property_names(self):
        return super()._config_property_names + ["param2", "param3"]


class TestReloadableModel(TestCase):
    info_data_dict = {
        # "id" and "my_id" not defined, key "0" will be used as id
        # (List will be converted to dict using model's "_property_names")
        0: [None, "value1_0", None, "value3_0"],
        # We can set id by special "my_id" attribute...
        # (All int ids will be stringified)
        "some": {"my_id": 1, "base": "0", "param1": "value1_1", "param2": "value2_1"},
        # ... as well as common with "id" attribute
        # (Nesting inheritance "any" -> "some" -> "0")
        "any": {"id": 2, "base": "some", "param1": "value1_2", "param4": "value4_2"},
        # "3" won't be created because "my_id" is defined (to 1) in "some"
        # (Aliases work with dict's keys, not with "id" or "my_id" attribute values)
        "3": "some",
        # Create "4" based on "0"
        4: 0,
        # Overwrite params of "4"
        "5": {"my_id": 4, "param3": "value3_5"}
    }
    resulted_info_data_dict = {"0": {"param1": "value1_0", "param3": "value3_0"},
                               "some": {"my_id": 1, "param1": "value1_1", "param2": "value2_1", "param3": "value3_0"},
                               "any": {"my_id": 2, "base": "some", "param1": "value1_2", "param4": "value4_2"},
                               "3": "some",
                               "4": 0,
                               "5": {"my_id": 4, "param3": "value3_5"}}

    info_data_list = [[None, "value1_0", None, "value3_0"],
                      {"my_id": "1", "base": "0", "param1": "value1_1", "param2": "value2_1"},
                      {"id": 2, "base": 1, "param1": "value1_2", "param4": "value4_2"},
                      "1",
                      0,
                      {"my_id": 4, "param3": "value3_5"}]
    resulted_info_data_list = {"0": {"param1": "value1_0", "param3": "value3_0"},
                               "1": {"my_id": "1", "param1": "value1_1", "param2": "value2_1", "param3": "value3_0"},
                               "2": {"my_id": 2, "base": 1, "param1": "value1_2", "param4": "value4_2"},
                               "3": "1",
                               "4": 0,
                               "5": {"my_id": 4, "param3": "value3_5"}}
    expected_list = [
        {"my_id": "0", "param1": "value1_0", "param2": None, "param3": "value3_0"},
        {"my_id": "1", "param1": "value1_1", "param2": "value2_1", "param3": "value3_0"},
        {"my_id": "2", "param1": "value1_2", "param2": "value2_1", "param3": "value3_0"},
        {"my_id": "4", "param1": "value1_0", "param2": None, "param3": "value3_5"},
    ]

    info_data_local_dict = {"0": ["value001_0", "value002_0"],
                            "some": {"my_id": 1, "param1": "value001_1"},
                            "any": {"id": 2, "param2": "value001_2", "param3": "value003_2"}}
    info_data_local_list = [["value001_0", "value002_0"],
                            {"my_id": 1, "param1": "value001_1"},
                            {"id": 2, "param2": "value001_2", "param3": "value003_2"}]

    def setUp(self):
        super().setUp()
        MyReloadableModel.model_class = MySubReloadableModel

    def tearDown(self):
        super().tearDown()
        MyReloadableModel.is_change_on_command = False
        MyReloadableModel.dispose_models()
        # ReloadableModel.dispose_models()
        self.assertIsNone(MyReloadableModel.model_class)
        # MyReloadableModel.model_class = None

    # Class/Static

    def test_on_configs_reloaded_with_dict(self):
        MyReloadableModel.on_configs_reloaded(self.info_data_dict)

        # resulted_info_data = {str(key): value for key, value in self.info_data_dict.items()}
        self.do_test_on_configs_reloaded(self.info_data_dict, self.resulted_info_data_dict)
        self.do_test_models(MySubReloadableModel.model_list, MySubReloadableModel.model_by_id)

    def test_on_configs_reloaded_with_list(self):
        MyReloadableModel.on_configs_reloaded(self.info_data_list)

        self.do_test_on_configs_reloaded(self.info_data_list, self.resulted_info_data_list)
        self.do_test_models(MySubReloadableModel.model_list, MySubReloadableModel.model_by_id)

    def do_test_on_configs_reloaded(self, info_data, resulted_info_data=None):
        self.assertEqual(MyReloadableModel._info_by_id, resulted_info_data)
        self.assertEqual(len(MyReloadableModel.model_list), 4)
        self.assertEqual(len(MyReloadableModel.model_by_id), 4)

        # Model type
        for model in MyReloadableModel.model_list:
            self.assertIsInstance(model, MySubReloadableModel)

        # Related classes
        self.assertIs(MySubReloadableModel._info_by_id, MyReloadableModel._info_by_id)
        self.assertEqual(len(MySubReloadableModel.model_list), 4)
        self.assertEqual(len(MySubReloadableModel.model_by_id), 4)

        self.assertIsNone(ReloadableModel._info_by_id)
        self.assertIsNone(ReloadableModel.model_list)
        self.assertIsNone(ReloadableModel.model_by_id)

    def do_test_models(self, model_list, model_by_id, expected_list=None):
        expected_list = expected_list or self.expected_list

        for i, model in enumerate(model_list):
            expected = expected_list[i]
            self.assert_model_matches(model, expected)

            self.assertIs(model.id, model.my_id)
            self.assertIs(model, model_by_id[model.id])
            self.assertFalse(model.is_marked_for_delete)

    def test_dispose_models(self):
        MyReloadableModel.on_configs_reloaded(self.info_data_dict)

        self.assertIsNotNone(MyReloadableModel._info_by_id)
        self.assertEqual(len(MyReloadableModel.model_list), 4)
        self.assertEqual(len(MyReloadableModel.model_by_id), 4)
        ReloadableModel.model_class = 1
        MyReloadableModel.model_class = 2

        MyReloadableModel.dispose_models()

        self.assertIsNone(MyReloadableModel._info_by_id)
        self.assertIsNone(MyReloadableModel.model_list)
        self.assertIsNone(MyReloadableModel.model_by_id)
        self.assertIsNone(MyReloadableModel.model_class)
        self.assertEqual(ReloadableModel.model_class, 1)
        ReloadableModel.model_class = None

    def test_create_model(self):
        self.assertEqual(ReloadableModel.model_class, None)

        self.assertIsInstance(ReloadableModel.create_model(None), ReloadableModel)

        ReloadableModel.model_class = MyReloadableModel

        self.assertIsInstance(ReloadableModel.create_model(None), MyReloadableModel)

    def test_prepare_info_data(self):
        input = None
        expected = None

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = []
        expected = {}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = {}
        expected = {}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = [0, "a", [1, 2], {"b": 4}]
        expected = {"0": 0, "1": "a", "2": [1, 2], "3": {"b": 4}}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = {3: 0, "u": "a", 5: [1, 2], "7": {"b": 4}}
        expected = {"3": 0, "u": "a", "5": [1, 2], "7": {"b": 4}}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = 100
        expected = {"0": 100}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

        input = "100"
        expected = {"0": "100"}

        self.assertEqual(ReloadableModel.prepare_info_data(input), expected)

    def test_update_model_list_with_default_id_name(self):
        temp = MyReloadableModel.id_name
        MyReloadableModel.id_name = ReloadableModel.id_name
        self.assertEqual(MyReloadableModel.id_name, "id")

        info_data_dict = {"any": {"id": 2, "param1": "value1_2", "param4": "value4_2"}}
        MyReloadableModel.on_configs_reloaded(info_data_dict)
        model_list = []
        model_by_id = {}

        MyReloadableModel.update_model_list(model_list, model_by_id, info_data_dict,
                                            MySubReloadableModel)

        expected = {"id": "2", "param1": "value1_2", "param2": None, "param3": None}
        self.assert_model_matches(model_list[0], expected)

        MyReloadableModel.id_name = temp

    def test_update_model_list_not_using_copies(self):
        MyReloadableModel.on_configs_reloaded(self.info_data_dict)
        MyReloadableModel.model_by_id["0"].param2 = "value1_0_current"
        model_list = []
        model_by_id = {}

        MyReloadableModel.update_model_list(model_list, model_by_id, self.info_data_dict,
                                            MySubReloadableModel)

        self.do_test_models(model_list, model_by_id)
        for model in model_list:
            # Different model instance with same id
            self.assertIsNot(model, MyReloadableModel.model_by_id[model.id])
            # Completely new instance, not a copy
            self.assertIsNone(model.parent_model)
            self.assertEqual(model.derived_models, [])

        # is_change_on_command
        MyReloadableModel.is_change_on_command = True
        MyReloadableModel.update_model_list(model_list, model_by_id,
                                            {0: [None, "value1_0__changed"], "6": {"base": 0}},
                                            MySubReloadableModel)

        model0 = model_by_id["0"]
        expected0 = {"my_id": "0", "param1": "value1_0__changed", "param2": None, "param3": "value3_0"}

        self.assert_model_matches(model0, expected0)

    def test_update_model_list_using_copies(self):
        MyReloadableModel.on_configs_reloaded(self.info_data_dict)
        MyReloadableModel.model_by_id["0"].param2 = "value2_0_current"
        model_list = []
        model_by_id = {}
        expected_list = self.expected_list
        expected_list[0] = expected_list[0].copy()
        expected_list[0]["param2"] = "value2_0_current"

        MyReloadableModel.update_model_list(model_list, model_by_id, self.info_data_dict,
                                            MySubReloadableModel, True)

        self.do_test_models(model_list, model_by_id, expected_list)
        for model in model_list:
            # Different model instance with same id
            self.assertIsNot(model, MyReloadableModel.model_by_id[model.id])
            # A copy of one of global models
            self.assertIsNotNone(model.parent_model)
            self.assertIn(model, model.parent_model.derived_models)

        # Reload + create new without parent_model
        MyReloadableModel.update_model_list(model_list, model_by_id,
                                            {0: [None, "value1_0_Changed"], "6": {"base": 0}},
                                            MySubReloadableModel, True)

        model0 = model_by_id["0"]
        model6 = model_by_id["6"]
        expected0 = {"my_id": "0", "param1": "value1_0_Changed", "param2": "value2_0_current", "param3": "value3_0"}
        expected6 = {"my_id": "6", "param1": "value1_0", "param2": None, "param3": "value3_0"}

        self.assertIsNotNone(model0.parent_model)
        self.assertIsNone(model6.parent_model)
        self.assert_model_matches(model0, expected0)
        self.assert_model_matches(model6, expected6)

        # is_change_on_command
        MyReloadableModel.is_change_on_command = True
        MyReloadableModel.update_model_list(model_list, model_by_id,
                                            {0: [None, "value1_0__changed"], "6": {"base": 0}},
                                            MySubReloadableModel, True)

        model0 = model_by_id["0"]
        expected0 = {"my_id": "0", "param1": "value1_0__changed", "param2": "value2_0_current", "param3": "value3_0"}

        self.assert_model_does_not_match(model0, expected0)

        model0.apply_changes()

        self.assert_model_matches(model0, expected0)

    def test_get_model_by_id(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})
        model = MyReloadableModel.get_model_by_id(0)
        submodel = MySubReloadableModel.get_model_by_id(0)

        self.assertTrue(model)
        self.assertIs(model, MyReloadableModel.get_model_by_id("0"))
        self.assertIs(model, submodel)
        self.assertEqual(model.param1, "value1_0")

    def test_get_model_copy_by_id(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})
        model = MyReloadableModel.get_model_by_id("0")
        model_copy = MyReloadableModel.get_model_copy_by_id("0")
        nomodel_copy = MyReloadableModel.get_model_copy_by_id("id_with_no_model")

        self.assertIsNone(nomodel_copy)
        self.assertTrue(model_copy)
        self.assertIsNot(model_copy, MyReloadableModel.get_model_copy_by_id(0))
        self.assertEqual(model_copy.param1, "value1_0")
        self.assertEqual(model_copy.param1, "value1_0")
        # Copy is a model with parent_model
        self.assertTrue(model_copy.parent_model)
        self.assertEqual(model_copy.parent_model, model)
        self.assertEqual(model_copy.parent_model.param1, "value1_0")

    def test_is_available(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})

        model = MyReloadableModel.get_model_by_id("0")
        self.assertFalse(MyReloadableModel.is_available_if_deleting)

        # is_marked_for_delete
        self.assertTrue(model.is_available)

        model.is_marked_for_delete = True

        self.assertFalse(model.is_available)

        # is_marked_for_delete + is_available_if_deleting
        MyReloadableModel.is_available_if_deleting = True

        self.assertTrue(model.is_available)

        # is_marked_deleted
        model.is_marked_for_delete = False
        model.is_marked_deleted = True

        self.assertFalse(model.is_available)

        MyReloadableModel.is_available_if_deleting = False

        self.assertFalse(model.is_available)

    def test_is_marked_for_delete(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})

        model = MyReloadableModel.get_model_by_id("0")
        model_copy = MyReloadableModel.get_model_copy_by_id("0")

        self.assertFalse(model.is_marked_for_delete)
        self.assertFalse(model_copy.is_marked_for_delete)

        model.is_marked_for_delete = True

        self.assertTrue(model.is_marked_for_delete)
        self.assertTrue(model_copy.is_marked_for_delete)

        model.is_marked_for_delete = False
        model_copy.is_marked_for_delete = True

        self.assertFalse(model.is_marked_for_delete)
        self.assertTrue(model_copy.is_marked_for_delete)

    def test_id(self):
        model = MyReloadableModel({"my_id": "0110"})

        self.assertEqual(model.id_name, "my_id")
        self.assertEqual(model.id, "0110")
        self.assertEqual(model.my_id, "0110")

        model = MyReloadableModel({"param1": "value"})
        model.id = "0110"

        self.assertEqual(model.id, None)
        self.assertEqual(model.my_id, None)

        model.id_name = "id"
        self.assertEqual(model.id, "0110")

    def test_init(self):
        model = MyReloadableModel([None, "value1_0"])

        self.assertEqual(model.param1, "value1_0")
        self.assertEqual(model.derived_models, [])

        MyReloadableModel.on_configs_reloaded({1: [None, "value1_1"]})

        model = MyReloadableModel("1")

        self.assertEqual(model.param1, "value1_1")

    def test_init_with_is_change_on_command(self):
        MyReloadableModel.is_change_on_command = True
        model = MyReloadableModel(["0", "value1_0"])

        self.assertEqual(model.id, "0")
        self.assertEqual(model.param1, "value1_0")
        self.assertEqual(model.derived_models, [])

        # (Don't create model by alias, use MyModel.get_model_by_id() or get_model_copy_by_id() instead!)
        # MyReloadableModel.on_configs_reloaded({1: [1, "value1_1"]})
        #
        # model = MyReloadableModel("1")
        #
        # self.assertEqual(model.id, "0")
        # self.assertEqual(model.param1, "value1_1")

    def test_dispose_derived(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})
        model = MyReloadableModel.get_model_by_id("0")
        model_copy = MyReloadableModel.get_model_copy_by_id("0")
        model.dispose = Mock(side_effect=model.dispose)

        # Ensure
        self.assertEqual(model_copy.parent_model, model)
        self.assertEqual(model.derived_models, [model_copy])

        # Dispose copy (derived)
        model_copy.dispose()

        self.assertEqual(model_copy.parent_model, None)
        self.assertEqual(model.derived_models, [])
        model.dispose.assert_not_called()

    def test_dispose_super(self):
        MyReloadableModel.on_configs_reloaded({0: [None, "value1_0"]})
        model = MyReloadableModel.get_model_by_id("0")
        model_copy = MyReloadableModel.get_model_copy_by_id("0")
        # model_copy.dispose = Mock(side_effect=model_copy.dispose)

        # Ensure
        self.assertEqual(model_copy.parent_model, model)
        self.assertEqual(model.derived_models, [model_copy])

        # Dispose global (parent_model)
        model.dispose()

        self.assertEqual(model_copy.parent_model, None)
        self.assertEqual(model.derived_models, [])
        # model_copy.dispose.assert_called_once()

    def test_reload(self):
        MyReloadableModel.on_configs_reloaded({"1": [None, "value1_1"]})
        model = MyReloadableModel(["0", "value1_0"])

        self.assertEqual(model.id, "0")
        self.assertEqual(model.param1, "value1_0")

        model.on_reload("1")

        self.assertEqual(model.id, "0")
        self.assertEqual(model.param1, "value1_1")

        MyReloadableModel.is_change_on_command = True

        model.on_reload({"param1": "value1_3"})

        self.assertEqual(model.param1, "value1_1")

        model.apply_changes()

        self.assertEqual(model.param1, "value1_3")

    def test_copy(self):
        model = MyReloadableModel(["0", "value1_0"])
        model.param1 = "value1_0_changed"
        expected = {"my_id": "0", "param1": "value1_0_changed"}

        model_copy = model.copy()

        self.assert_model_matches(model_copy, expected)
        self.assert_model_matches(model, expected)
        self.assertEqual(model._initial_config, model_copy._initial_config)
        self.assertIs(model_copy.parent_model, model)
        self.assertIn(model_copy, model.derived_models)

    def test_import_data(self):
        model = MyReloadableModel(["0", "value1_0"])
        model_copy = model.copy()
        update_data = {"param1": "value1_0_changed"}
        expected = {"my_id": "0", "param1": "value1_0_changed"}

        model.import_data(update_data)

        self.assert_model_matches(model, expected)
        self.assert_model_matches(model_copy, expected)

    def test_get_info_by_id(self):
        MyReloadableModel._info_by_id = {"some": "any"}
        model = MyReloadableModel()

        with patch("napalm.utils.object_util.get_info_by_id") as mock:
            model.get_info_by_id("12")
            mock.assert_called_once_with(MyReloadableModel._info_by_id, "12", model._property_names)


    def test_resolve_info(self):
        MyReloadableModel._info_by_id = {"some": "any"}
        model = MyReloadableModel()

        with patch("napalm.utils.object_util.resolve_info") as mock:
            model.resolve_info("12")
            mock.assert_called_once_with(MyReloadableModel._info_by_id, "12", model._property_names)

    # Utility

    def assert_model_matches(self, model, expected_dict):
        for key, value in expected_dict.items():
            self.assertEqual(getattr(model, key), value, str(model.id) + "|" + str(key))

    def assert_model_does_not_match(self, model, expected_dict):
        for key, value in expected_dict.items():
            if getattr(model, key) != value:
                return
        self.fail("Model matches dict")


class MyReloadableMultiModel(ReloadableMultiModel):
    param1 = "01"
    param2 = "02"
    param3 = "03"
    param4 = "04"
    param5 = "05"

    @property
    def _config_property_names(self):
        return ["id", "param1", "param2", "param3", "param4", "param5"]


class TestReloadableMultiModel(TestCase):
# ?
# class TestReloadableMultiModel(TestReloadableModel):

    def setUp(self):
        super().setUp()

        MyReloadableMultiModel.on_configs_reloaded([[0, 1, 2], [1, None, None, 3, 4], [2, None, 22, 33]])

    def tearDown(self):
        super().tearDown()

        MyReloadableMultiModel.dispose_models()
        # Restore defaults
        MyReloadableMultiModel.is_change_on_command = False
        MyReloadableMultiModel.use_copies_for_sub_models = True

    def test_create_multimodel_by_ids(self):
        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])

        self.assertIsInstance(model, MyReloadableMultiModel)
        self.assertEqual(model.ids, [0, 1, 2, 5])
        self.assertEqual(len(model._sub_models), 3)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        model = ReloadableMultiModel.create_multimodel_by_ids([])

        self.assertIsInstance(model, ReloadableMultiModel)

        ReloadableMultiModel.model_class = MyReloadableMultiModel
        model = ReloadableMultiModel.create_multimodel_by_ids(None)

        self.assertIsInstance(model, MyReloadableMultiModel)

    def test_id(self):
        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])

        self.assertIsNone(model.id)

        model = MyReloadableMultiModel(["some"], [0, 1, 2, 5])

        self.assertEqual(model.id, "some")

        model.ids = [2, 1]
        model.apply_changes()

        self.assertEqual(model.id, "some")

    def test_is_changed(self):
        self.assertFalse(MyReloadableMultiModel.is_change_on_command)

        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])

        self.assertFalse(model.is_changed)

        # Change as a regular ReloadableModel
        model.import_data([None, 10])

        self.assertFalse(model.is_changed)

        # Change as ReloadableMultiModel
        sub_model0 = MyReloadableMultiModel.get_model_by_id("0")
        sub_model0.import_data([None, 100])

        self.assertFalse(model.is_changed)

        # Change ids
        model.ids = [0, 1]

        self.assertFalse(model.is_changed)

    def test_is_changed_if_is_change_on_command(self):
        MyReloadableMultiModel.use_copies_for_sub_models = False
        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])
        model.is_change_on_command = True

        self.assertFalse(model.is_changed)

        # Change as a regular ReloadableModel
        model.import_data([None, 10])

        self.assertTrue(model.is_changed)

        model.apply_changes()

        self.assertFalse(model.is_changed)

        # Change as ReloadableMultiModel
        sub_model0 = MyReloadableMultiModel.get_model_by_id("0")
        sub_model0.is_change_on_command = True
        sub_model0.import_data([None, 100])

        self.assertTrue(model.is_changed)

        model.apply_changes()

        self.assertFalse(model.is_changed)

        # # Import same data -> is_changed=True
        # sub_model0.import_data([None, 100])
        #
        # self.assertTrue(model.is_changed)
        #
        # model.apply_changes()
        # # (new)
        sub_model0.import_data([None, 100])

        self.assertFalse(model.is_changed)

        # Change ids
        model.ids = [0, 1]

        self.assertTrue(model.is_changed)

        model.apply_changes()

        self.assertFalse(model.is_changed)

        # Same ids
        model.ids = [0, 1]

        self.assertFalse(model.is_changed)

    def test_ids(self):
        self.assertFalse(MyReloadableMultiModel.is_change_on_command)
        model = MyReloadableMultiModel()

        # Three valid and one wrong sub_model id
        model.ids = [0, "1", 2, 5]

        self.assertEqual(model.ids, [0, "1", 2, 5])
        self.assertEqual(len(model._sub_models), 3)
        self.assertEqual([sub_model.id for sub_model in model._sub_models], ["0", "1", "2"])

        # is_change_on_command
        model.is_change_on_command = True
        model.ids = [2, 4]

        self.assertTrue(model.is_changed)
        self.assertEqual(model.ids, [2, 4])
        self.assertEqual(len(model._sub_models), 1)
        self.assertEqual([sub_model.id for sub_model in model._sub_models], ["2"])

    def test_ids_and_applying_changes(self):
        self.assertFalse(MyReloadableMultiModel.is_change_on_command)

        # Setter
        model = MyReloadableMultiModel()
        model.ids = [2, 1]

        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, [2, 1])
        self.assertEqual(model.export_data(), [None, "01", 22, 3, 4, "05", []])  # changes applied at once

        # Set empty - don't affect properties
        model.ids = []

        self.assertEqual(model.ids, [])
        self.assertEqual(model._sub_models, [])
        self.assertEqual(model.export_data(), [None, "01", 22, 3, 4, "05", []])  # no changes

        # Set None
        model.ids = [2, 1]
        self.assertEqual(len(model._sub_models), 2)

        model.ids = None

        self.assertEqual(model.ids, None)
        self.assertEqual(model._sub_models, [])
        self.assertEqual(model.export_data(), [None, "01", 22, 3, 4, "05", []])  # no changes

        # is_change_on_command
        model.is_change_on_command = True
        model.ids = [1, 2, 0]

        self.assertTrue(model.is_changed)
        self.assertEqual(model.ids, [1, 2, 0])
        self.assertEqual(model.export_data(), [None, "01", 22, 3, 4, "05", []])  # no changes

        model.apply_changes()

        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, [1, 2, 0])
        self.assertEqual(model.export_data(), [None, 1, 2, 33, 4, "05", []])  # changes applied

        # Same ids - ignore
        model.ids = [1, 2, 0]

        self.assertFalse(model.is_changed)

        # (Not same ids)
        model.ids = ["1", 2, 0]

        self.assertTrue(model.is_changed)

    def test_use_copies_for_sub_models(self):
        # use_copies_for_sub_models=True (default)
        self.assertEqual(MyReloadableMultiModel.use_copies_for_sub_models, True)
        model = MyReloadableMultiModel(ids=[0, "1", 2, 5])

        self.assertNotEqual(model._sub_models[0], MyReloadableMultiModel.get_model_by_id("0"))  # copy

        # use_copies_for_sub_models=False
        MyReloadableMultiModel.use_copies_for_sub_models = False
        model.ids = [0, "1", 2]

        self.assertEqual(model._sub_models[0], MyReloadableMultiModel.get_model_by_id("0"))  # same

    def test_constructor(self):
        # Empty ids
        model = MyReloadableMultiModel()

        self.assertEqual(model.ids, None)
        self.assertEqual(model._sub_models, [])
        self.assertEqual(model._initial_config, None)
        self.assertEqual(model.export_data(), [None, "01", "02", "03", "04", "05", []])

        # Wrong sub_model ids
        model = MyReloadableMultiModel(ids=["55", 77])

        self.assertEqual(model.ids, ["55", 77])
        self.assertEqual(model._sub_models, [])
        self.assertEqual(model.export_data(), [None, "01", "02", "03", "04", "05", []])

        # Three valid and one wrong sub_model id
        model = MyReloadableMultiModel(ids=[0, "1", 2, 5])

        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, [0, "1", 2, 5])
        self.assertEqual([sub_model.id for sub_model in model._sub_models], ["0", "1", "2"])
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # is_change_on_command
        MyReloadableMultiModel.is_change_on_command = True
        model = MyReloadableMultiModel(ids=[0, "1", 2, 5])

        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, [0, "1", 2, 5])
        self.assertEqual([sub_model.id for sub_model in model._sub_models], ["0", "1", "2"])
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

    def test_dispose(self):
        model = MyReloadableMultiModel.create_multimodel_by_ids([0, "1", 2, 5])
        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, [0, "1", 2, 5])
        self.assertEqual([sub_model.id for sub_model in model._sub_models], ["0", "1", "2"])
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        model.dispose()

        self.assertFalse(model.is_changed)
        self.assertEqual(model.ids, None)
        self.assertEqual(model._sub_models, [])
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])  # not changed

        model.reset()

        self.assertEqual(model.export_data(), [None, "01", "02", "03", "04", "05", []])

    def test_apply_changes(self):
        self.assertFalse(MyReloadableMultiModel.is_change_on_command)

        MyReloadableMultiModel.use_copies_for_sub_models = False
        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # (initial_config set on constructor)
        model.param1 = 101
        self.assertEqual(model.export_data(), [None, 101, 22, 33, 4, "05", []])

        model.reset()

        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # Change as a regular ReloadableModel
        model.import_data([None, 10, None, None, None, 50])

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, 50, []])

        # (import_data() doesn't affect on initial_config)
        model.reset()

        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # Change as ReloadableMultiModel
        sub_model2 = MyReloadableMultiModel.get_model_by_id("2")
        sub_model2.is_change_on_command = True
        sub_model2.import_data([None, 100])
        sub_model2.param2 = 200
        self.assertTrue(model.is_changed)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])  # not changed

        model.apply_changes()

        self.assertEqual(model.export_data(), [None, 100, 200, 33, 4, "05", []])  # changed

        # (sub_model.import_data() doesn't affect on initial_config)
        model.reset()

        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # Change ids
        model.ids = [0, 2]

        self.assertFalse(model.is_changed)
        # self.assertEqual(model.export_data(), [None, 1, 22, 33, None, []])
        # (Note: indeed all changes are applied over previous setups. None cannot overwrite 4)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # # (ids property changes initial_config)
        # model.reset()
        #
        # self.assertEqual(model.export_data(), [None, 1, 22, 33, None, []])

    def test_apply_changes_if_is_change_on_command(self):
        # (To get model's submodel by MyReloadableMultiModel.get_model_by_id())
        MyReloadableMultiModel.use_copies_for_sub_models = False
        MyReloadableMultiModel.is_change_on_command = True

        model = MyReloadableMultiModel.create_multimodel_by_ids([0, 1, 2, 5])

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 4, "05", []])

        # Change as a regular ReloadableModel
        model.import_data([None, 10])

        self.assertTrue(model.is_changed)
        self.assertEqual(model.export_data()[:-1], [None, 1, 22, 33, 4, "05"])  # not changed

        model.apply_changes()

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 10, 22, 33, 4, "05", []])  # changed

        # Change as ReloadableMultiModel
        sub_model2 = MyReloadableMultiModel.get_model_by_id("2")
        sub_model2.param2 = 200
        sub_model2.import_data([None, 100])

        self.assertTrue(model.is_changed)
        self.assertEqual(model.export_data(), [None, 10, 22, 33, 4, "05", []])  # not changed

        model.apply_changes()

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 100, 200, 33, 4, "05", []])  # changed

        # Change ids
        model.ids = [0, 2]

        self.assertTrue(model.is_changed)
        self.assertEqual(model.export_data(), [None, 100, 200, 33, 4, "05", []])  # not changed

        # (Yet nothing changes initial_config till now)
        model.reset()
        self.assertEqual(model.export_data(), [None, 1, 22, 33, "04", "05", []])

        model.apply_changes()

        self.assertFalse(model.is_changed)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, "04", "05", []])  # changed
        # self.assertEqual(model.export_data(), [None, 1, 22, 33, None, "05", []])  # changed
        #
        # # (Only ids property changes initial_config)
        # model.reset()
        #
        # self.assertEqual(model.export_data(), [None, 1, 22, 33, None, "05", []])

    def test_reset(self):
        # Create
        MyReloadableMultiModel.use_copies_for_sub_models = False
        # (1, 2 - submodels ids)
        model = MyReloadableMultiModel({"param1": 101, "param4": 404}, [1, 2])

        self.assertEqual(model.export_data(), [None, 101, 22, 33, 4, "05", []])

        # Change
        model.param4 = 400
        sub_model2 = MyReloadableMultiModel.get_model_by_id("2")
        sub_model2.is_change_on_command = True
        sub_model2.import_data([None, None, None, 300])
        sub_model2.param2 = 200
        model.apply_changes()
        model.param1 = 100

        self.assertEqual(model.export_data(), [None, 100, 200, 300, 4, "05", []])

        # Reset
        model.reset()

        self.assertEqual(model.export_data(), [None, 101, 22, 33, 4, "05", []])

    def test_copy(self):
        # use_copies_for_sub_models=True (default)
        model = MyReloadableMultiModel({"param1": 101, "param4": 404}, [0, 2, 5])
        model_copy = model.copy()

        self.assertFalse(model.is_change_on_command)
        self.assertNotEqual(model, model_copy)
        self.assertEqual(model, model_copy.parent_model)
        self.assertIn(model_copy, model.derived_models)
        self.assertEqual(model_copy.ids, [0, 2, 5])
        self.assertNotEqual(model._sub_models, model_copy._sub_models)
        self.assertEqual([sub_model.id for sub_model in model_copy._sub_models], ["0", "2"])

        self.assertEqual(model.export_data(), [None, 1, 22, 33, 404, "05", []])
        self.assertEqual(model_copy.export_data(), [None, 1, 22, 33, 404, "05", []])

        model.import_data({"param1": 100, "param4": 400})

        # (1 in submodel overwrites just imported 100)
        self.assertEqual(model.export_data(), [None, 1, 22, 33, 400, "05", []])
        self.assertEqual(model_copy.export_data(), [None, 1, 22, 33, 400, "05", []])

        model.reset()

        self.assertEqual(model.export_data(), [None, 1, 22, 33, 404, "05", []])
        self.assertEqual(model_copy.export_data(), [None, 1, 22, 33, 400, "05", []])

        model_copy.reset()

        self.assertEqual(model_copy.export_data(), [None, 1, 22, 33, 404, "05", []])

        # use_copies_for_sub_models=False
        MyReloadableMultiModel.use_copies_for_sub_models = False
        model = MyReloadableMultiModel({"param1": 101, "param4": 404}, [0, 2, 5])
        model_copy = model.copy()

        self.assertNotEqual(model, model_copy)
        self.assertEqual(model._sub_models, model_copy._sub_models)  # same sub_models!
        self.assertEqual(model_copy.ids, [0, 2, 5])
        self.assertEqual([sub_model.id for sub_model in model_copy._sub_models], ["0", "2"])
