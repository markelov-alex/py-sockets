from unittest import TestCase

from napalm.utils import object_util


class Values:
    a = None
    b = None
    c = None
    e = None

    def __init__(self, a=5, b=6, c=7, e=8):
        self.a = a
        self.b = b
        self.c = c
        self.e = e


class TestSetUpObject(TestCase):
    # Test None params

    def test_set_up_object_with_empty_params_and_value_list(self):
        # Set up
        dic = None
        value_list = [5, 6, 7]
        property_name_list = ["a", "b"]
        expected_dic = None

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_list = None
        property_name_list = ["a", "b"]
        expected_dic = {"a": 1, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_list = [5, 6, 7]
        property_name_list = None
        expected_dic = {"a": 1, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_with_empty_params_and_value_dict(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_dic = {"a": 5, "c": None, "e": 8}
        property_name_list = None
        expected_dic = {"a": 5, "b": 2, "c": 3, "e": 8}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

        # Test empty dic
        # Set up
        dic = {}
        value_dic = {"a": 5, "c": 7, "e": None}
        property_name_list = None
        expected_dic = {"a": 5, "c": 7}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_with_empty_params_and_value_obj(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_obj = Values(c=None)  # {"a": 5, "c": None, "e": 8}
        property_name_list = None
        expected_dic = {"a": 1, "b": 2, "c": 3}  # {"a": 5, "b": 2, "c": 3, "e": 8}

        # Assert
        object_util.set_up_object(dic, value_obj)
        self.assertEqual(dic, expected_dic)

        # Test empty dic
        # Set up
        dic = {}
        value_obj = Values(e=None)  # {"a": 5, "c": 7, "e": None}
        property_name_list = None
        expected_dic = {}  # {"a": 5, "c": 7}

        # Assert
        object_util.set_up_object(dic, value_obj)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_dic_with_value_list(self):
        # Test dic as obj and values as list

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_list = [5, None, 7]
        property_name_list = ["a", "b"]
        expected_dic = {"a": 5, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

        self.assertEqual(obj.a, 1)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)
        object_util.set_up_object(obj, value_list, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)

    def test_set_up_object_dic_with_value_dic(self):
        # Test dic as obj and values as dict

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_dic = {"a": 5, "c": None, "e": 8}
        property_name_list = ["a", "b", "c"]
        expected_dic = {"a": 5, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_dic, property_name_list)
        self.assertEqual(dic, expected_dic)

        object_util.set_up_object(obj, value_dic, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_dic = {"a": 5, "c": 7, "e": 8}
        property_name_list = None
        expected_dic = {"a": 5, "b": 2, "c": 7, "e": 8}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

        object_util.set_up_object(obj, value_dic, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 7)

    def test_set_up_object_dic_with_value_obj(self):
        # Test dic as obj and values as dict

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_obj = Values(b=None, c=None)  # {"a": 5, "c": None, "e": 8}
        property_name_list = ["a", "b", "c"]
        expected_dic = {"a": 5, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_obj, property_name_list)
        self.assertEqual(dic, expected_dic)

        object_util.set_up_object(obj, value_obj, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)

    def test_set_up_object_on_object_without_setter(self):
        # Test obj without setter and values as dict

        # Set up
        obj = PropertyObject()
        value_list = [5, 6, 7]
        property_name_list = ["a", "b", "c"]

        # Assert
        self.assertEqual(obj.a, 1)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)
        object_util.set_up_object(obj, value_list, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 6)
        self.assertEqual(obj.c, 3)

        # Set up
        obj = PropertyObject()
        value_dic = {"a": 5, "b": 6, "c": 7, "e": 8}
        property_name_list = ["a", "b", "c"]

        # Assert
        object_util.set_up_object(obj, value_dic, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 6)
        self.assertEqual(obj.c, 3)

        # Set up
        obj = PropertyObject()
        value_dic = {"a": 5, "b": 6, "c": 7, "e": 8}
        property_name_list = None

        # Assert
        object_util.set_up_object(obj, value_dic, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 6)
        self.assertEqual(obj.c, 3)

    def test_set_up_object_with_referenced_values_in_dic(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_dic = {"a": [1, 2, {"u": "x"}], "b": {2: 3, "4": 5, "u": SimpleObject(55)}}
        expected_dic = {"a": [1, 2, {"u": "x"}], "b": {2: 3, "4": 5, "u": SimpleObject(55)}, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

        # Changes in dic should not affect value_dic
        dic["a"].append(3)
        dic["b"]["6"] = 7
        # (More nested)
        dic["a"][2]["u"] = "yy"
        dic["b"]["u"].a = "zz"
        self.assertEqual(value_dic["a"], [1, 2, {"u": "x"}])
        self.assertEqual(value_dic["b"], {2: 3, "4": 5, "u": SimpleObject(55)})

        # Assert (if values are the same, then expected are the same too)
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_with_referenced_values_in_list(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_list = [[1, 2, {"u": "x"}], {2: 3, "4": 5, "u": SimpleObject(55)}]
        property_name_list = ["a", "b", "c"]
        expected_dic = {"a": [1, 2, {"u": "x"}], "b": {2: 3, "4": 5, "u": SimpleObject(55)}, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

        # Changes in dic should not affect value_dic
        dic["a"].append(3)
        dic["b"]["6"] = 7
        # (More nested)
        dic["a"][2]["u"] = "yy"
        dic["b"]["u"].a = "zz"
        self.assertEqual(value_list[0], [1, 2, {"u": "x"}])
        self.assertEqual(value_list[1], {2: 3, "4": 5, "u": SimpleObject(55)})

        # Assert (if values are the same, then expected are the same too)
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_with_referenced_values_in_obj(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_obj = Values(a=[1, 2, {"u": "x"}], b={2: 3, "4": 5, "u": SimpleObject(55)}, c=None, e=None)
        property_name_list = ["a", "b", "c"]
        expected_dic = {"a": [1, 2, {"u": "x"}], "b": {2: 3, "4": 5, "u": SimpleObject(55)}, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_obj, property_name_list)
        self.assertEqual(dic, expected_dic)

        # Changes in dic should not affect value_dic
        dic["a"].append(3)
        dic["b"]["6"] = 7
        # (More nested)
        dic["a"][2]["u"] = "yy"
        dic["b"]["u"].a = "zz"
        self.assertEqual(value_obj.a, [1, 2, {"u": "x"}])
        self.assertEqual(value_obj.b, {2: 3, "4": 5, "u": SimpleObject(55)})

        # Assert (if values are the same, then expected are the same too)
        object_util.set_up_object(dic, value_obj, property_name_list)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_with_defaults_to_skip(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_dic = {"a": 21, "b": 22, "c": 23}
        defaults = {"a": 1, "b": 22, "c": 23}
        expected_dic = {"a": 21, "b": 2, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_dic, defaults_to_skip=defaults)
        self.assertEqual(dic, expected_dic)


class TestObjectToPlainList(TestCase):
    def test_object_to_plain_list(self):
        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        property_name_list = ["d", "a", "c"]

        # Assert
        result = object_util.object_to_plain_list(dic, property_name_list)
        self.assertEqual(result, [None, 1, 3])

        # Set up
        obj = SimpleObject()
        property_name_list = ["b", "d", "a", "c"]

        # Assert
        result = object_util.object_to_plain_list(dic, property_name_list)
        self.assertEqual(result, [2, None, 1, 3])

        # Set up
        obj = PropertyObject()
        property_name_list = ["b", "d", "a", "c"]

        # Assert
        result = object_util.object_to_plain_list(dic, property_name_list)
        self.assertEqual(result, [2, None, 1, 3])

    def test_object_to_plain_list_with_empty_params(self):
        # Set up
        dic = None
        property_name_list = ["d", "a", "c"]

        # Assert
        result = object_util.object_to_plain_list(dic, property_name_list)
        self.assertEqual(result, None)

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        property_name_list = None

        # Assert
        result = object_util.object_to_plain_list(dic, property_name_list)
        self.assertEqual(result, None)


class TestGetKeyByValue(TestCase):
    def test_get_key_by_value(self):
        # Set up
        obj = {"a": 1, "b": 2, "c": 3, "d": 4}
        # print(self, "(test_get_key_by_value)", obj)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj = SimpleObject()
        # print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj = PropertyObject()
        # print(self, "(test_get_key_by_value)", obj.__dict__, vars(obj), dir(obj))

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj_list = [PropertyObject(), {"e": 1, "f": 2, "g": 3, "h": 4}]
        # print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj_list), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj_list), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj_list), "c")

        # Set up
        obj_list = ({"e": 1, "f": 2, "g": 3, "h": 4}, PropertyObject())
        # print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj_list), "e")
        self.assertEqual(object_util.get_key_by_value(2, obj_list), "f")
        self.assertEqual(object_util.get_key_by_value(3, obj_list), "g")


class TestObjectToDict(TestCase):
    def test_object_to_dict(self):
        # Set up
        obj = {"a": 1, "b": 2, "c": 3, "d": 4}
        # print(self, "(test_object_to_dict)", obj)

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4})

        # Set up
        obj = SimpleObject()
        # print(self, "(test_object_to_dict)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4, "f": 6})

        # Set up
        obj = PropertyObject()
        # print(self, "(test_object_to_dict)", obj.__dict__, vars(obj), dir(obj))

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4})


class TestGetObjectById(TestCase):
    info_by_id = None
    property_names = None

    def setUp(self):
        super().setUp()
        self.info_by_id = {
            "simple": {
                "lobby_id": "simple",
                "lobby_name": "Lobby S",
                "rooms": [1, 2]
            },
            "1": {
                "base": "5",
                "lobby_id": "11",
                "lobby_name": None,
                "rooms": None
            },
            "2": {
                "base": 3,
                "lobby_id": 2,
                "lobby_name": "Lobby 2",
                "rooms": None
            },
            "3": [
                3,
                "Lobby 3",
                [6, 7, 8]
            ],
            "4": "1",
            "5": "2"
        }
        self.property_names = ["lobby_id", "lobby_name", "rooms"]

    def test_empty_args(self):
        # None without info_by_id
        info = object_util.get_info_by_id(None, None)
        expected = None

        self.assertEqual(info, expected)

        # None without info_by_id
        info = object_util.get_info_by_id(None, "1")
        expected = None

        self.assertEqual(info, expected)

    def test_get_info_from_object(self):
        info = object_util.get_info_by_id(self.info_by_id, "simple", self.property_names)
        expected = {
            "lobby_id": "simple",
            "lobby_name": "Lobby S",
            "rooms": [1, 2]
        }

        self.assertEqual(info, expected)
        self.assertIs(info, self.info_by_id["simple"])

    def test_get_info_from_array(self):
        info = object_util.get_info_by_id(self.info_by_id, "3", self.property_names)
        # expected = [3, "Lobby 3", [6, 7, 8]]
        expected = {
            "lobby_id": 3,
            "lobby_name": "Lobby 3",
            "rooms": [6, 7, 8]
        }

        self.assertEqual(info, expected)
        self.assertIs(info, self.info_by_id["3"])

    def test_str_and_not_str_id(self):
        info = object_util.get_info_by_id(self.info_by_id, 1, self.property_names)
        info2 = object_util.get_info_by_id(self.info_by_id, "1", self.property_names)

        self.assertEqual(info, info2)
        self.assertIs(info, info2)

    def test_aliases(self):
        info = object_util.get_info_by_id(self.info_by_id, 1, self.property_names)
        # By alias
        info2 = object_util.get_info_by_id(self.info_by_id, 4, self.property_names)
        # Alias cached
        info3 = self.info_by_id["4"]

        self.assertEqual(info, info2)
        self.assertIs(info, info2)
        self.assertEqual(info, info3)
        self.assertIs(info, info3)

    def test_inheritance(self):
        info = object_util.get_info_by_id(self.info_by_id, "2", self.property_names)
        # Resolved cached
        info2 = self.info_by_id["2"]
        expected = {
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8]
        }

        self.assertEqual(info, expected)
        self.assertEqual(info, info2)
        self.assertIs(info, info2)

    def test_nested_inheritance_and_aliases(self):
        info = object_util.get_info_by_id(self.info_by_id, "4", self.property_names)
        # Resolved cached
        info1 = self.info_by_id["1"]
        info2 = self.info_by_id["2"]
        info3 = self.info_by_id["3"]
        # Result cached
        info4 = self.info_by_id["4"]
        expected1 = {
            "lobby_id": "11",
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8]
        }
        expected2 = {
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8]
        }
        # -expected3 = [
        #     3,
        #     "Lobby 3",
        #     [6, 7, 8]
        # ]
        expected3 = {
            "lobby_id": 3,
            "lobby_name": "Lobby 3",
            "rooms": [6, 7, 8]
        }

        self.assertEqual(info1, expected1)
        self.assertEqual(info2, expected2)
        self.assertEqual(info3, expected3)
        self.assertEqual(info, info1)
        self.assertEqual(info, info4)
        self.assertIs(info, info1)
        self.assertIs(info, info4)


class TestResolveBase(TestCase):
    info_by_id = None
    property_names = None

    def setUp(self):
        super().setUp()
        self.info_by_id = {
            "1": {
                "lobby_id": "11",
                "lobby_name": "",
                "rooms": None
            },
            "2": {
                "base": 3,
                "lobby_id": 2,
                "lobby_name": "Lobby 2",
                "rooms": None,
                "some": 222
            },
            "3": [
                3,
                "Lobby 3",
                [6, 7, 8],
                None,
                "4"
            ],
            "4": "1",
            "5": "2"
        }
        self.property_names = ["lobby_id", "lobby_name", "rooms", "some", "base"]

    def test_empty_args(self):
        # None for None
        info = object_util.resolve_info(None, None)
        expected = None

        self.assertEqual(info, expected)

        # No changes for dict
        info = object_util.resolve_info(None, self.info_by_id["2"])
        expected = {
            "base": 3,
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": None,
            "some": 222
        }

        self.assertEqual(info, expected)

        # None if id given
        info = object_util.resolve_info(None, "3")
        expected = None

        self.assertEqual(info, expected)

        # Converting list to dict is possible without info_by_id
        info = object_util.resolve_info(None, self.info_by_id["3"], self.property_names)
        expected = {
            "lobby_id": 3,
            "lobby_name": "Lobby 3",
            "rooms": [6, 7, 8],
            # "some": None,
            "base": "4"
        }

        self.assertEqual(info, expected)

        # No converting without property_names
        info = object_util.resolve_info(None, self.info_by_id["3"])
        expected = {}

        self.assertEqual(info, expected)

    def test_inheritance_by_id(self):
        # info = object_util.resolve_info(self.info_by_id, self.info_by_id["2"], self.property_names)
        info = object_util.resolve_info(self.info_by_id, "2", self.property_names)
        info2 = self.info_by_id["2"]
        expected = {
            "base": 3,
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8],
            "some": 222
        }

        self.assertEqual(info, expected)
        # (resolve_info don't cache)
        self.assertEqual(info, info2)
        # self.assertIs(info, info2)

    def test_inheritance_by_value(self):
        info = object_util.resolve_info(self.info_by_id, self.info_by_id["2"], self.property_names)
        info2 = self.info_by_id["2"]
        expected = {
            "base": 3,
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8],
            "some": 222
        }

        self.assertEqual(info, expected)
        # (resolve_info don't cache)
        self.assertNotEqual(info, info2)
        self.assertIsNot(info, info2)

    def test_array_to_object_with_inheritance(self):
        info = object_util.resolve_info(self.info_by_id, self.info_by_id["3"], self.property_names)
        # ("some": 222 - inherited from "2")
        expected = {
            "lobby_id": 3,
            "lobby_name": "Lobby 3",
            "rooms": [6, 7, 8],
            # "some": 222,
            "base": "4"
        }

        self.assertEqual(info, expected)

    def test_nested_inheritance_and_aliases(self):
        info = object_util.resolve_info(self.info_by_id, "5", self.property_names)

        # Resolved cached
        info1 = self.info_by_id["1"]
        info2 = self.info_by_id["2"]
        info3 = self.info_by_id["3"]
        # Result cached
        info4 = self.info_by_id["4"]
        info5 = self.info_by_id["5"]
        expected5 = {
            "base": 3,
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8],
            "some": 222
        }
        expected2 = {
            "base": 3,
            "lobby_id": 2,
            "lobby_name": "Lobby 2",
            "rooms": [6, 7, 8],
            "some": 222
        }
        expected3 = {
            "base": "4",
            "lobby_id": 3,
            "lobby_name": "Lobby 3",
            "rooms": [6, 7, 8],
            # "some": 222
        }

        self.assertEqual(info, expected5)
        # self.assertEqual(info1, expected1)
        self.assertEqual(info2, expected2)
        self.assertEqual(info3, expected3)
        self.assertEqual(info2, info5)
        self.assertIs(info1, info4)


# Mock(?) objects

class SimpleObject:
    f = 6

    def __init__(self, a=1):
        self.a = a
        self.b = 2
        self.c = 3
        self.d = 4

    def __eq__(self, o: object) -> bool:
        return isinstance(o, type(self)) and self.a == o.a and \
               self.b == o.b and self.c == o.c and self.d == o.d


class PropertyObject:
    def __init__(self):
        self.a = 1
        self.__b = 2
        self.__c = 3
        self.d = 4

    @property
    def b(self):
        return self.__b

    @b.setter
    def b(self, value):
        self.__b = value

    # Note: Getter only!
    @property
    def c(self):
        return self.__c

    def method(self):
        pass
