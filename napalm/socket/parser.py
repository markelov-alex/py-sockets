import json


class CommandParser:
    EMPTY = ""  # "-1"

    # 37||243||0::David,,David Federman,, ... ,,80;;3::Chris,,Chris Mattaboni,, ... ,,80##
    COMMAND_DELIM = "##"
    PARAMS_DELIM = "||"

    COMPLEX_LIST_DELIM = ";;"
    DICT_KEY_DELIM = "::"
    LIST_DELIM = ",,"

    AUTO_REPLACE = {"&dblsharp&": COMMAND_DELIM, "&dblstick&": PARAMS_DELIM,
                    "&dblsemi&": COMPLEX_LIST_DELIM, "&dblcolon&": DICT_KEY_DELIM,
                    "&dblcomma&": LIST_DELIM}

    # Parse

    @staticmethod
    def parse_room_code(room_code):
        """
        :param room_code: possible values "1_10_0", "1_10_", "1_10", "1__", "1_", "1", or ""
               empty position means any value (converted to -1 int value)
        :return:
        # tests
        print("!!!!! parse_room_code", parser.parse_room_code("1_10_0"), "|", 1,10,0)
        print("!!!!!!parse_room_code", parser.parse_room_code("1_10_"), 1,10,-1)
        print("!!!!!!parse_room_code", parser.parse_room_code("1_10"), 1,10,-1)
        print("!!!!!!parse_room_code", parser.parse_room_code("1__"), 1,-1,-1)
        print("!!!!!!parse_room_code", parser.parse_room_code("1_"), 1,-1,-1)
        print("!!!!!!parse_room_code", parser.parse_room_code("1"), 1,-1,-1)
        print("!!!!! parse_room_code", parser.parse_room_code(""), -1,-1,-1)
        """
        if not room_code:
            return -1, -1, -1

        room_code_array = room_code.split("_")
        items_count = len(room_code_array)
        game_id = int(room_code_array[0]) if items_count >= 1 and room_code_array[0] else -1
        game_type = int(room_code_array[1]) if items_count >= 2 and room_code_array[1] else -1
        room_type = int(room_code_array[2]) if items_count >= 3 and room_code_array[2] else -1
        return game_id, game_type, room_type

    def split_commands(self, commands_data):
        return commands_data.split(self.COMMAND_DELIM)

    def parse_command(self, command):
        param_list = command.split(self.PARAMS_DELIM)
        # print("#[protocol] (parse_command) command:", command, "param_list:", param_list)

        for index, param in enumerate(param_list):
            if self.COMPLEX_LIST_DELIM in param:
                sublist = None
                subdict = None
                if self.DICT_KEY_DELIM in param:
                    # "k1::a,,b,,c;;k2::;;k3::v3" -> {"k1": ["a", "b", "c"], "k2": None, "k3": "v3"}
                    subdict = {}
                    for subitem in sublist.values():
                        # "k1::a,,b,,c" -> ["k1", "a,,b,,c"]
                        key_value_list = subitem.split(self.DICT_KEY_DELIM)
                        key = key_value_list[0]
                        value = key_value_list[1] if len(key_value_list) > 1 else None
                        # "a,,b,,c" -> ["a", "b", "c"]
                        if self.LIST_DELIM in value:
                            value = value.split(self.LIST_DELIM)
                        # {..., "k1": ["a", "b", "c"]}
                        subdict[key] = value
                elif self.LIST_DELIM in param:
                    # "a,,b,,c,,d;;abc;;d,,e,,f;;g,,h" -> [["a", "b", "c", "d"], "abc", ["d", "e", "f"], ["g", "h"]]
                    sublist = param.split(self.COMPLEX_LIST_DELIM)
                    for key, subitem in sublist.items():
                        if self.LIST_DELIM in subitem:
                            # "a,,b,,c,,d" -> [..., ["a", "b", "c", "d"]]
                            sublist[key] = subitem.split(self.LIST_DELIM)
                param_list[index] = subdict or sublist
            elif self.LIST_DELIM in param:
                # "a,,b,,c" -> ["a", "b", "c"]
                param_list[index] = param.split(self.LIST_DELIM)

        return param_list

    def decode_string(self, string):
        # "some&dblstick&text" -> "some||text"
        for old, new in self.AUTO_REPLACE.items():
            string = str(string).replace(old, new)
        return string

    # Serialize

    def encode_string(self, string):
        # "some||text" -> "some&dblstick&text"
        for new, old in self.AUTO_REPLACE.items():
            string = str(string).replace(old, new)
        return string

    def join_commands(self, command_data_list):
        # return self.COMMAND_DELIM.join(command_data_list)
        return "".join(command_data_list)

    def make_command(self, command_params):
        """
        command_params = ["10", [3, 100, 200], 50, [[23123, "name1", 2000], [65332, "name2", 2300]],
                            {"0": "some", 5: ["a", "b", 7]}]
        return "10||3,,100,,200||50||23123,,name1,,2000;;65332,,name2,,2300||0::some;;5::a,,b,,7"

        command_params' items can be int, str, list or dict; list's and dict's can have plain lists as items
        """
        # Serialize each param
        # print("P (make_command)", "command_params:", command_params)
        for index, param in enumerate(command_params):
            # print("P  (make_command)", "index:", index, "param:", param)
            if isinstance(param, dict):
                # Param is dict (possibly with lists as values)
                command_params[index] = self._serialize_dict(param)
            elif isinstance(param, list):
                # Param is complex (with lists as items) or plain list
                # was
                is_complex = False
                if len(param) > 0:
                    for item in param:
                        is_complex = isinstance(item, list)
                        # print("P   (make_command)", "item:", item, "is_complex:", isinstance(item, list), is_complex)
                        break
                # is_complex = any([isinstance(item, list) for item in param])
                # print("#temp (make_command) list:", param, "is_complex:", is_complex, isinstance(param[0], list))
                # print("P  (make_command)", "param:", param, "is_complex:", is_complex)
                if not is_complex:
                    param = self._str_items(param)
                command_params[index] = self._serialize_complex_list(param) \
                    if is_complex else self.LIST_DELIM.join(param)

        command_params = [str(item if item is not None else "") for item in command_params]
        return self.PARAMS_DELIM.join(command_params) + self.COMMAND_DELIM

    def _str_items(self, items):
        return [json.dumps(item) if isinstance(item, list) or isinstance(item, dict)
                else str(int(item) if isinstance(item, bool) else (item if item is not None else ""))
                for item in items]

    def _serialize_dict(self, dic):
        # {"k1": "v1", "k2": ["a", "b", "c"]} -> ["k1::v1", "k2::a,,b,,c"]
        items = [str(key) + self.DICT_KEY_DELIM +
                 (self.LIST_DELIM.join([str(val_item) for val_item in value]) if isinstance(value, list) else
                  str(value if value is not None else ""))
                 for key, value in dic.items()]
        # ["k1::v1", "k2::a,,b,,c"] -> "k1::v1;;k2::a,,b,,c"
        return self.COMPLEX_LIST_DELIM.join(items)

    def _serialize_complex_list(self, complex_list):
        # -print("#Parser _serialize_complex_list", "complex_list:", complex_list)
        # [["a", "b", "c", ["a", 2, ""], 10], "v1"] -> ["a,,b,,c,,['a', 2, ''],,10", "v1"]

        # [[1, 'room1', '1_10_0', [25, 50, -1, -1, '', 0, 0], 6, -1, 0, 0, 0], ...] ->
        #   '1,,room1,,1_10_0,,[25, 50, -1, -1, "", 0, 0],,6,,-1,,0,,0,,0;;...'
        # Note: JSON format needs "". For '' JSON parser throws an exception.
        # (in python str([25, 50, -1, -1, "", 0, 0]) will return "[25, 50, -1, -1, '', 0, 0]",
        # but JSON parser on client expects '[25, 50, -1, -1, "", 0, 0]')
        items = [self.LIST_DELIM.join(self._str_items(value))
                 if isinstance(value, list) else str(value if value is not None else "")
                 for value in complex_list]

        # -print("# Parser _serialize_complex_list items:", len(items),[isinstance(item, str) for item in items],items)
        # -print("#  Parser _serialize_complex_list result:",self.COMPLEX_LIST_DELIM.join(items))

        # ["a,,b,,c,,['a', 2, ''],,10", "v1"] -> "a,,b,,c,,['a', 2, ''],,10;;v1"
        return self.COMPLEX_LIST_DELIM.join(items)
