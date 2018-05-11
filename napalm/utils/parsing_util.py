import sys


# todo use standard getopt library, for example
def get_command_line_param(key, default=None):
    """
    Get param value from sys.argv.
    For example:
    for "-a -b 2"
    get_command_line_param("-a")     # -> True
    get_command_line_param("-a", 5)  # -> 5
    get_command_line_param("-b")     # -> "2"
    get_command_line_param("-b", 5)  # -> "2"
    get_command_line_param("-c")     # -> False
    get_command_line_param("-c", 5)  # -> 5
    :param key:
    :param default:
    :return:
    """
    if key not in sys.argv:
        return default
    param_index = sys.argv.index(key) + 1

    # Return True if has key but no param value
    if param_index >= len(sys.argv):
        return default or True

    param = sys.argv[param_index]
    # Check that param value is not another argument
    return default or True if param.startswith("-") else param
