from unittest import TestCase

from napalm.utils import object_util


class TestSetUpObject(TestCase):

    def test_set_up_object_with_empty_params(self):
        # Test None params

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

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        value_dic = {"a": 5, "c": 7, "e": 8}
        property_name_list = None
        expected_dic = {"a": 5, "b": 2, "c": 7, "e": 8}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

        # Test empty dic
        # Set up
        dic = {}
        value_dic = {"a": 5, "c": 7, "e": 8}
        property_name_list = None
        expected_dic = {"a": 5, "c": 7, "e": 8}

        # Assert
        object_util.set_up_object(dic, value_dic)
        self.assertEqual(dic, expected_dic)

    def test_set_up_object_dic_with_value_list(self):
        # Test dic as obj and values as list

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_list = [5, 6, 7]
        property_name_list = ["a", "b"]
        expected_dic = {"a": 5, "b": 6, "c": 3}

        # Assert
        object_util.set_up_object(dic, value_list, property_name_list)
        self.assertEqual(dic, expected_dic)

        self.assertEqual(obj.a, 1)
        self.assertEqual(obj.b, 2)
        self.assertEqual(obj.c, 3)
        object_util.set_up_object(obj, value_list, property_name_list)
        self.assertEqual(obj.a, 5)
        self.assertEqual(obj.b, 6)
        self.assertEqual(obj.c, 3)

    def test_set_up_object_dic_with_value_dic(self):
        # Test dic as obj and values as dict

        # Set up
        dic = {"a": 1, "b": 2, "c": 3}
        obj = SimpleObject()
        value_dic = {"a": 5, "c": 7, "e": 8}
        property_name_list = ["a", "b"]
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
        obj = {"a": 1, "b": 2,  "c": 3,  "d": 4}
        print(self, "(test_get_key_by_value)", obj)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj = SimpleObject()
        print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj = PropertyObject()
        print(self, "(test_get_key_by_value)", obj.__dict__, vars(obj), dir(obj))

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj), "c")

        # Set up
        obj_list = [PropertyObject(), {"e": 1, "f": 2,  "g": 3,  "h": 4}]
        print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj_list), "a")
        self.assertEqual(object_util.get_key_by_value(2, obj_list), "b")
        self.assertEqual(object_util.get_key_by_value(3, obj_list), "c")

        # Set up
        obj_list = ({"e": 1, "f": 2, "g": 3, "h": 4}, PropertyObject())
        print(self, "(test_get_key_by_value)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.get_key_by_value(1, obj_list), "e")
        self.assertEqual(object_util.get_key_by_value(2, obj_list), "f")
        self.assertEqual(object_util.get_key_by_value(3, obj_list), "g")


class TestObjectToDict(TestCase):
    def test_object_to_dict(self):
        # Set up
        obj = {"a": 1, "b": 2, "c": 3, "d": 4}
        print(self, "(test_object_to_dict)", obj)

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4})

        # Set up
        obj = SimpleObject()
        print(self, "(test_object_to_dict)", obj.__dict__)

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4, "f": 6})

        # Set up
        obj = PropertyObject()
        print(self, "(test_object_to_dict)", obj.__dict__, vars(obj), dir(obj))

        # Assert
        self.assertEqual(object_util.object_to_dict(obj), {"a": 1, "b": 2, "c": 3, "d": 4})


# Mock(?) objects

class SimpleObject:
    f = 6

    def __init__(self):
        self.a = 1
        self.b = 2
        self.c = 3
        self.d = 4


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

