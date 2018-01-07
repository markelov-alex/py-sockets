def set_up_object(obj, values, property_name_list=None, is_verbose=False):
    """
    set_up_object({"a": 1, "b":2, "c": 3}, [5, 6, 7], ["a", "b"]) => obj={"a": 5, "b":6, "c": 3}
    set_up_object({"a": 1, "b":2, "c": 3}, {"a": 5, "c": 7, "e": 8}, ["a", "b"]) =>
    obj={"a": 5, "b":2, "c": 3}
    set_up_object({"a": 1, "b":2, "c": 3}, {"a": 5, "c": 7, "e": 8}) => obj={"a": 5, "b":2, "c": 7}

    :param obj: dict or any object
    :param values: value_dict - get value by property name from property_name_list or
    plain_value_list - get value of property by same index as in property_name_list
    :param property_name_list:
    :param is_verbose: print warnings if some property or its setter missing
    :return:
    """

    plain_value_list = values if isinstance(values, list) or isinstance(values, tuple) else None
    value_dict = values if isinstance(values, dict) else None
    if not property_name_list and value_dict:
        property_name_list = value_dict.keys()

    if obj is None or (not plain_value_list and not value_dict) or not property_name_list:
        return

    value_list_len = len(plain_value_list) if plain_value_list else 0
    for index, property_name in enumerate(property_name_list):
        if not property_name:
            continue

        if plain_value_list:
            value = plain_value_list[index] if index < value_list_len else None
        else:
            value = value_dict[property_name] if property_name in value_dict else None
        # Don't overwrite with empty value
        if value is not None and value != "":
            if isinstance(obj, dict):  # -and property_name in obj
                obj[property_name] = value
            elif hasattr(obj, property_name):
                try:
                    setattr(obj, property_name, value)
                except AttributeError as err:
                    # (If there is no setter)
                    if is_verbose:
                        print("R Warning. Property_name:", property_name, err, "value:", value)
            elif is_verbose:
                print("R Warning! There is no property with name:", property_name, "in room instance:", obj)


def object_to_plain_list(obj, property_name_list):
    """
    {"a": 1, "b": 2}, ["c", "a"] -> [None, 1]
    :param obj: dict or any object with attributes
    :param property_name_list:
    :return:
    """
    if not obj or not property_name_list:
        return None

    if isinstance(obj, dict):
        return [obj[property_name] if property_name in obj else None
                for property_name in property_name_list]
    return [getattr(obj, property_name) if hasattr(obj, property_name) else None
            for property_name in property_name_list]
#
#
# def object_to_plain_list(obj, property_name_list, exclude_property_name_list=None, bool_excluded=False):
#     if not obj or not property_name_list:
#         return None
#
#     return [getattr(obj, property_name)
#             if not exclude_property_name_list or property_name not in exclude_property_name_list
#             else (int(bool(getattr(obj, property_name))) if bool_excluded else None)
#             for property_name in property_name_list]


def get_key_by_value(value, lookups):
    if not value or not lookups:
        return None

    lookup_list = lookups
    if not isinstance(lookups, list) and not isinstance(lookups, tuple):
        lookup_list = (lookups,)

    for lookup in lookup_list:
        # (Doesn't cover @property)
        # if not isinstance(lookup, dict):
        #     lookup = lookup.__dict__

        if not isinstance(lookup, dict):
            key_list = dir(lookup)
            for key in key_list:
                if not key.startswith("_") and getattr(lookup, key) == value:
                    return key
        else:
            for key, item_value in lookup.items():
                if item_value == value and not key.startswith("_"):
                    return key

    return None


def object_to_dict(obj):
    if isinstance(obj, dict):
        return obj

    # (Doesn't cover @property)
    # return obj.__dict__

    key_list = dir(obj)
    return {key: getattr(obj, key) for key in key_list
            if not key.startswith("_") and not hasattr(getattr(obj, key), "__call__")}
