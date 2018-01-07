import atexit

from napalm.async import Timer, TwistedTimer
from napalm.socket.server import ThreadedTCPServer, TwistedTCPServer
from napalm.utils import object_util


class SocketGameApplication:

    def __init__(self, lobby_model, server_class=ThreadedTCPServer):
        self.lobby_model = lobby_model

        # Choose timer implementation for current server type
        if server_class == TwistedTCPServer:
            self.lobby_model.timer_class = TwistedTimer

        # Create play logic
        self.lobby = self.lobby_model.lobby_class(lobby_model)
        # Create server
        self.server = server_class(self)

        # todo check
        # Save state on exit (Doesn't work in PyCharm)
        if self.lobby_model.save_lobby_state_enabled and self.lobby_model.save_lobby_state_on_exit:
            atexit.register(self.lobby.save_lobby_state)

    # ?
    # def dispose(self):
    #     self.server_config = None
    #
    #     self.lobby.dispose()
    #     self.lobby = None
    #
    #     self.server
    #     self.server = None

    def __repr__(self):
        address = self.lobby_model.host + ":" + str(self.lobby_model.port) if self.lobby_model else ""
        return "<{0} lobby_id:{1} address:{2} server:{3}>".format(
            self.__class__.__name__, self.lobby_model.lobby_id if self.lobby_model else "-",
            address, self.server.__class__.__name__ if hasattr(self, "server") and self.server else "-")

    def start(self):
        self.lobby.start()
        self.server.start()


class ConfigurableMixIn:
    """
    Functionality to configure instance by config params list which is set on creation.
    You can always reset instance properties to initial config state by calling reset() method.

    If you set initial_config as plain value list you need to define _config_property_name_list.
    If initial_config set as dict _config_property_name_list is not necessary, but it's useful
    if you want to set some specified properties, not all.
    """

    # Override
    @property
    def _config_property_name_list(self):
        """
        Mention here all model's property names. Applying initial_config should fit the order of this list.

        Rule 1: keep order same as in json config files (servers.json, rooms.json, games.json)
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return []

    def __init__(self, initial_config):
        """
        :param initial_config: a list of property values in order of self._config_property_name_list
                             or a dict of property values with property names from self._config_property_name_list
        """
        self._initial_config = initial_config
        self._apply_initial_config()

    def _apply_initial_config(self):
        object_util.set_up_object(self, self._initial_config, self._config_property_name_list)

    # Override
    def reset(self):
        """
        Some params could be changed during the program's work.
        This methods make us able to reset all params to initial.

        Usually called on play restart, for example.
        """
        self._apply_initial_config()


class ExportableMixIn:
    """
    Export/import instance state functionality to be added to class as mix-in.

    Can be serialized to plain_list and restored back whenever it's needed.
    List all properties you want to serialize/restore in _export_property_name_list.
    List all properties you want to send to client in _public_export_property_name_list.
    Reset all needed state properties in overriden reset() method.

    Class implements Memento design pattern.
    """

    # Override
    @property
    def _export_property_name_list(self):
        """
        List of property names to be saved on server (only for internal use).
        This properties won't be sent to client.

        Rule 1: keep order same as between save/restore cycle. There is no special need to keep order
        because it's for internal needs only (if _public_export_property_name_list doesn't use this)
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return []

    # Override
    @property
    def _public_export_property_name_list(self):
        """
        For client! Always sync changes in client's code!

        List of property names to be sent to client. So be careful to avoid sending some secret information
        about other players (for example, other players' cards, or contents of current deck of cards).

        Rule 1: keep order same as on client
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return self._export_property_name_list

    def export_data(self, is_public=True):
        """
        Serialize current model state to plain list in order of self._export_property_name_list
        (or self._public_export_property_name_list if is_public=True).

        Used:
         1) to update remote app state on client (is_public=True) or
         2) to save current state to restore it later, for example, after server restart (is_public=False)
        """
        return object_util.object_to_plain_list(self, self._public_export_property_name_list
                                                if is_public else self._export_property_name_list)

    def import_data(self, data_list):
        """
        Import saved state (should be saved using export_data(is_public=False).
        Properties are parsed in order of self._export_property_name_list.

        Used to restore model, for example, after server restart.
        :param data_list:
        :return:
        """
        object_util.set_up_object(self, data_list, self._export_property_name_list)

    # Override
    def reset(self):
        """
        Override to reset state properties.
        """
        pass


class BaseModel(ConfigurableMixIn, ExportableMixIn):
    """
    Base class for models to contain object's initial configuration and current state.

    Can be configured on start and serialized whenever it's needed.
    Configuration may change during the work, but you can always reset the model
    to initial configuration and zero state at any time.

    Class implements Memento design pattern through ExportableMixIn.
    """

    # Override
    @property
    def _export_property_name_list(self):
        return self._config_property_name_list
