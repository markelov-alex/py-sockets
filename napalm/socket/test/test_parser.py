from unittest import TestCase

from napalm.socket.parser import CommandParser


class TestCommandParser(TestCase):
    def setUp(self):
        super().setUp()
        self.parser = CommandParser()

    def test_parse_room_code(self):
        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1_7_10_5")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, 7)  # can be numeric
        self.assertEqual(game_type, 10)
        self.assertEqual(room_type, 5)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1_H_10_5")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, "H")
        self.assertEqual(game_type, 10)
        self.assertEqual(room_type, 5)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1_H_10_")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, "H")
        self.assertEqual(game_type, 10)
        self.assertEqual(room_type, -1)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1_H_")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, "H")
        self.assertEqual(game_type, -1)
        self.assertEqual(room_type, -1)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1_")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, -1)
        self.assertEqual(game_type, -1)
        self.assertEqual(room_type, -1)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("1")
        self.assertEqual(game_id, 1)
        self.assertEqual(game_variation, -1)
        self.assertEqual(game_type, -1)
        self.assertEqual(room_type, -1)

        game_id, game_variation, game_type, room_type = CommandParser.parse_room_code("")
        self.assertEqual(game_id, -1)
        self.assertEqual(game_variation, -1)
        self.assertEqual(game_type, -1)
        self.assertEqual(room_type, -1)

    def test_make_room_code(self):
        room_code = CommandParser.make_room_code("1", "H", 10, 5)
        self.assertEqual(room_code, "1_H_10_5")

        room_code = CommandParser.make_room_code("1", "H", 10)
        self.assertEqual(room_code, "1_H_10")

        room_code = CommandParser.make_room_code("1", "H")
        self.assertEqual(room_code, "1_H")

        room_code = CommandParser.make_room_code("1")
        self.assertEqual(room_code, "1")

        room_code = CommandParser.make_room_code()
        self.assertEqual(room_code, "")

    def test_split_commands(self):
        commands = self.parser.split_commands("a||b||c##d||e||f||")
        self.assertEqual(commands, ["a||b||c", "d||e||f||"])

        commands = self.parser.split_commands("a||b||c##d||e||f||##")
        self.assertEqual(commands, ["a||b||c", "d||e||f||", ""])

    def test_parse_command(self):
        params_list = self.parser.parse_command(
            "1||k1::a,,b,,c;;k2::;;k3::v3;;k4||a,,b,,c,,d;;abc;;d,,e,,f;;g,,h||a,,b,,c")
        self.assertEqual(len(params_list), 4)
        self.assertEqual(params_list[0], "1")
        self.assertEqual(params_list[1], {"k1": ["a", "b", "c"], "k2": "", "k3": "v3", "k4": None})
        self.assertEqual(params_list[2], [["a", "b", "c", "d"], "abc", ["d", "e", "f"], ["g", "h"]])
        self.assertEqual(params_list[3], ["a", "b", "c"])

    def test_decode_string(self):
        string = self.parser.decode_string("some&dblstick&text")
        self.assertEqual(string, "some||text")

    def test_encode_string(self):
        string = self.parser.encode_string("some||text")
        self.assertEqual(string, "some&dblstick&text")

    def test_join_commands(self):
        commands = self.parser.join_commands(["1||param1||param2##", "4||param1||param2##"])
        self.assertEqual(commands, "1||param1||param2##4||param1||param2##")

    def test_make_command(self):
        command_params = self.parser.make_command(["10", [3, 100, 200], 50,
                                                   [[23123, "name1", 2000], [65332, "name2", 2300]]])
        self.assertEqual(command_params, "10||3,,100,,200||50||23123,,name1,,2000;;65332,,name2,,2300##")

        command_params = self.parser.make_command(["10", {"0": "some", 5: ["a", "b", 7]}])
        self.assertEqual(command_params, "10||0::some;;5::a,,b,,7##")

    # protected

    def test_str_items(self):
        items = self.parser._str_items(["abc", 123, True, False, None,
                                        ["abc", 123, True, False, None],
                                        {"a": "abc", "b": 123, "c": True, "d": False, "e": None}
                                        ])
        self.assertEqual(items, ["abc", "123", "1", "0", "",
                                 '["abc", 123, true, false, null]',
                                 '{"a": "abc", "b": 123, "c": true, "d": false, "e": null}'
                                 ])

    def test_serialize_dict(self):
        string = self.parser._serialize_dict({"k1": "v1", "k2": ["a", "b", "c"]})
        self.assertEqual(string, "k1::v1;;k2::a,,b,,c")

        # Note: due to performance we use str() instead of _str_items()
        # string = self.parser._serialize_dict({"k1": "v1", "k2": ["a", 2, ["a", 2, "", True, False, None]],
        #                                       "k3": 123, "k4": None, "k5": {"a": "abc", "d": False, "e": None}})
        # self.assertEqual(string, 'k1::v1;;k2::a,,2,,["a", 2, "", true, false, null];;
        # k3::123;;k4::;;k5::{"a": "abc", "d": false, "e": null}')
    
    def test_serialize_complex_list(self):
        string = self.parser._serialize_complex_list([["a", "b", "c", ["a", 2, ""], 10], "v1"])
        self.assertEqual(string, 'a,,b,,c,,["a", 2, ""],,10;;v1')

        # Note: due to performance we use str() instead of _str_items()
        # string = self.parser._serialize_complex_list([["a", "", 2, True, False, None,
        #                                                ["a", 2, "", True, False, None]],
        #                                               "v1"])
        # self.assertEqual(string, 'a,,,,2,,1,,0,,,,["a", 2, "", true, false, null];;v1')
