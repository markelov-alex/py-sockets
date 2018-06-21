import atexit
import collections
import json
import logging
import time

from napalm.async import TwistedTimer
from napalm.socket.server import ThreadedTCPServer, TwistedTCPServer
from napalm.utils import object_util


class SocketApplication:
    config = None
    server = None

    def __init__(self, config, server_class=ThreadedTCPServer):
        self.config = config

        # Choose timer implementation for chosen server type
        if issubclass(server_class, TwistedTCPServer):
            self.config.timer_class = TwistedTimer

        # Create server
        self.server = server_class(self.config, self)

    # todo add tests
    def dispose(self):
        if self.server:
            self.stop()

        self.config = None
        self.server = None

    def __repr__(self):
        class_name = self.__class__.__name__
        address = self.config.host + ":" + str(self.config.port) if self.config else ""
        server_class_name = self.server.__class__.__name__ if hasattr(self, "server") and self.server else "-"
        return "<{0} address:{1} server:{2}>".format(class_name, address, server_class_name)

    def start(self):
        self.server.start()

    # todo add tests
    def stop(self):
        self.server.stop()


class SocketGameApplication(SocketApplication):
    house = None

    def __init__(self, server_config, server_class=ThreadedTCPServer):
        super().__init__(server_config, server_class)

        # Create play logic
        if hasattr(self.config, "house_class"):
            self.house = self.config.house_class(self.config)

        # todo check
        # Save state on exit (Doesn't work from PyCharm)
        if hasattr(self.config, "is_save_house_state_enabled") and self.config.is_save_house_state_enabled and \
                self.config.is_save_house_state_on_exit:
            atexit.register(self.house.save_house_state)

    # todo add tests
    def dispose(self):
        super().dispose()

        self.house.dispose()
        self.house = None

    def __repr__(self):
        class_name = self.__class__.__name__
        house_id = self.config.house_id if self.config and hasattr(self.config, "house_id") else "-"
        address = self.config.host + ":" + str(self.config.port) if self.config else ""
        server_class_name = self.server.__class__.__name__ if hasattr(self, "server") and self.server else "-"
        return "<{0} house_id:{1} address:{2} server:{3}>".format(
            class_name, house_id, address, server_class_name)

    def start(self):
        self.house.start()
        super().start()

    # todo add tests
    def stop(self):
        self.house.stop()
        super().stop()


class ConfigurableMixIn:
    """
    Functionality to configure instance by config params list which is set on creation.
    You can always reset instance properties to initial config state by calling reset() method.

    If you set initial_config as plain list of values you need to define _config_property_names.
    If initial_config set as dict _config_property_names is not necessary, but it's useful
    if you want to set some specified properties, not all.
    """

    # Override
    @property
    def _config_property_names(self):
        """
        Enlist here all model's property names.

        Rule 1: keep order same as in json config files (servers.json, lobbies.json, games.json)
        Rule 2: keep names as they are in current model (subclasses of this class)
        """
        return []

    def __init__(self, initial_config):
        """
        :param initial_config: a list of property values in order of self._config_property_names
                             or a dict of property values with property names from self._config_property_names
        """
        self._initial_config = initial_config
        self._apply_initial_config()

    def _apply_initial_config(self):
        object_util.set_up_object(self, self._initial_config, self._config_property_names)

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

    Can be serialized to plain list and restored back whenever it's needed.
    Class implements Memento design pattern.

    List all properties you want to save/restore in _property_names.
    List all properties you want to send to client in _public_property_names.
    # Reset all needed state properties in overridden reset() method.
    """

    # If True, enqueue all imports and apply only on apply_changes().
    # Needed to apply new config reloaded between games, not during the game.
    is_change_on_command = False
    # Needed for all dependant models to know do they need to update their params.
    # (Example, each game has its own GameConfig which references on single global 
    # GameConfig instance. The global one could be reloaded and all others could 
    # take the changes when it is convenient.)
    change_time = None

    @property
    def is_changed(self):
        return bool(self._changes_queue)  # and len(self._changes_queue) > 0

    # Override
    @property
    def _property_names(self):
        """
        List of property names to be saved on server (only for internal use).
        This properties won't be sent to client, so they can contain private data.

        Rule 1: Keep order same as between save/restore cycle. There is no special need to keep order
        because it's for internal needs only (if _public_property_names doesn't use this).
        Rule 2: Keep names as they are in current model (subclasses of this class).
        """
        return []

    # Override
    @property
    def _public_property_names(self):
        """
        For client developers: Always sync changes in client's code!

        List of property names to be sent to client. So be careful to avoid sending some secret information
        about other players (for example, other players' cards, or contents of current deck of cards).

        Rule 1: Keep order same as on client.
        Rule 2: Keep names as they are in current model (subclasses of this class).
        """
        return self._property_names

    def __init__(self) -> None:
        super().__init__()
        self._changes_queue = []

    def export_data(self):
        """
        Serialize current model state to plain list in order of self._property_names.

        Used to save current state to restore it later, for example, after server restart.
        """
        return object_util.object_to_plain_list(self, self._property_names)

    def import_data(self, data):
        """
        Import saved state (should be saved using export_data()).
        Properties are parsed in order of self._property_names.

        Used to restore model, for example, after server restart.
        :param data:
        :return:
        """
        if self.is_change_on_command:
            if object_util.has_changes(self, data, self._property_names):
                # (Makes is_changed=True)
                self._changes_queue.append((data, self._property_names))
        else:
            # prev_id = self.id
            object_util.set_up_object(self, data, self._property_names)
            # self._check_id_changed(prev_id, self.id)
            self.change_time = time.time()

            # (For overriden apply_changes())
            self.apply_changes()

    def export_public_data(self):
        """
        Serialize current model state to plain list in order of self._public_property_names.

        Used to update remote app state on client.
        """
        return object_util.object_to_plain_list(self, self._public_property_names)

    def import_public_data(self, data_list):
        """
        Import state received from another server or client
        (should be saved using export_public_data()).
        Properties are parsed in order of self._property_names.

        Used to update state of current object, to synchronize states between clients and servers.
        :param data_list:
        :return:
        """
        if self.is_change_on_command:
            if object_util.has_changes(self, data_list, self._public_property_names):
                self._changes_queue.append((data_list, self._public_property_names))
        else:
            object_util.set_up_object(self, data_list, self._public_property_names)
            self.change_time = time.time()

    def apply_changes(self):
        # prev_id = self.id
        for data_list, property_names in self._changes_queue:
            object_util.set_up_object(self, data_list, property_names)
            self.change_time = time.time()
        # self._check_id_changed(prev_id, self.id)
        self._changes_queue.clear()

    # ?needed?
    # # Override
    # def reset(self):
    #     """
    #     Override to reset state properties.
    #     """
    #     pass


class BaseModel(ConfigurableMixIn, ExportableMixIn):
    """
    Base class for models to contain object's initial configuration and current state.

    Can be configured on start and serialized whenever it's needed.
    Configuration may change during the work, but you can always reset the model
    to initial configuration and zero state at any time.

    Class implements Memento design pattern through ExportableMixIn.
    """

    logging = None

    # Override
    @property
    def _property_names(self):
        # ("_changes_queue" added for cases when new config was loaded but not applied yet,
        # and in this position model was dumped for recovery. After recovery, we should
        # continue from the previous state and be able to apply changes which we could not
        # apply last time.)
        # todo add unittest for ["_changes_queue"]
        return self._config_property_names + ["_changes_queue"]

    def __init__(self, initial_config):
        ConfigurableMixIn.__init__(self, initial_config)
        ExportableMixIn.__init__(self)

        self.logging = logging.getLogger("MODEL")


class ReloadableModel(BaseModel):
    """
    The main concepts about models:

    Values could be changed during game and reset on game reset. For example,
    for long games temp can be increased, decreasing user turn time, or stakes can be
    increased on further rounds.

    Initial values could be loaded and reloaded from config files. Changes could be
    applied immediately or on demand. Load and reload is made from single point -
    HouseConfig, from where it is spread on all models automatically.

    Initial values of model considered as config. When we change values during game
    config becomes a model. Model could be reset to config by calling reset().

    ?--- Note: id can be reloaded. (Used in client models.)
    todo add blocking import if id changes on update
    """

    # Static
    model_class = None
    id_name = "id"
    # (Set after config for each model type to determine whether to show models which marked for delete)
    is_available_if_deleting = False

    _info_by_id = None
    model_list = None
    model_by_id = None

    @classmethod
    def on_configs_reloaded(cls, info_data):
        if not info_data:
            logging.error("Empty info_data on reload for %s!", cls)
            return

        cls._info_by_id = info_data = ReloadableModel.prepare_info_data(info_data)

        if not cls.model_list:
            cls.model_list = []
        if not cls.model_by_id:
            cls.model_by_id = {}

        cls.update_model_list(cls.model_list, cls.model_by_id, info_data, cls.model_class or cls)

    @classmethod
    def dispose_models(cls):
        if cls.model_list:
            # (list() needed to make a copy)
            for model in list(cls.model_list):
                model.dispose()
        cls._info_by_id = None
        cls.model_list = None
        cls.model_by_id = None
        cls.model_class = None

    @classmethod
    def create_model(cls, info):
        model_factory = cls.model_class or cls
        return model_factory(info)

    @staticmethod
    def prepare_info_data(info_data):
        if info_data is None:
            return None
        if isinstance(info_data, list):
            # list -> dict
            info_data = {str(index): info for index, info in enumerate(info_data)}
        elif isinstance(info_data, dict):
            # Stringify keys
            info_data = {str(key): info for key, info in info_data.items()}

        if not isinstance(info_data, collections.Iterable) or isinstance(info_data, str):
            info_data = {"0": info_data}
        return info_data

    @staticmethod
    def update_model_list(model_list, model_by_id, info_data, model_factory, use_copies=False):
        if not info_data or not model_factory:
            return
        if model_list is None or model_by_id is None:
            return
        # # (return them in the end)
        # if model_list is None:
        #     model_list = []
        # if model_by_id is None:
        #     model_by_id = {}

        # list|dict -> dict
        info_data = ReloadableModel.prepare_info_data(info_data)

        # (Needed because we cannot easily make class property (_property_names for resolve_info()))
        model_inst = model_factory(None)
        global_model_by_id = model_inst.model_by_id
        id_name = model_inst.id_name
        real_id_set = set()
        for id, info in info_data.items():
            # Normalize ids for correct inheritance (common -> custom id)
            if isinstance(info, dict) and "id" in info and info["id"] and id_name != "id":
                info[id_name] = info["id"]
                del info["id"]

            # (copy() needed to do not change id_name-property on next line)
            # (get_info_by_id() caches resolved values, but not working for creating submodels,
            # like for "rooms" in lobby info and "lobbies" in house info)
            info = model_inst.resolve_info(info)
            if not info:
                logging.error("Cannot resolve info with key: %s in info_data: %s", id, info_data)
                continue
            info = info.copy()
            # Get id or set default
            if id_name not in info or info[id_name] is None or info[id_name] == "":
                # Set if not defined
                id = info[id_name] = str(id)
            else:
                # Stringify id
                id = info[id_name] = str(info[id_name])
            real_id_set.add(id)

            if id not in model_by_id:
                if use_copies and id in global_model_by_id:  # and global_model_by_id
                    new_model = global_model_by_id[id].copy()
                else:
                    new_model = model_factory(info)
                if not new_model.id:
                    new_model.id = id
                model_by_id[id] = new_model
                model_list.append(new_model)
            else:
                model_by_id[id].on_reload(info)
                if not use_copies:
                    # Update global models immediately
                    model_by_id[id].apply_changes()

        # Mark deleting
        for model in model_list:
            # if model.id in current_ids:
            if model.id in real_id_set:
                # Restore
                model.is_marked_for_delete = model.is_marked_deleted = False
            elif not model.is_marked_deleted:
                # Mark to be deleted if haven't been already
                model.is_marked_for_delete = True

        # return model_list, model_by_id

    @classmethod
    def get_model_by_id(cls, id):
        id = str(id)
        return cls.model_by_id[id] if cls.model_by_id and id in cls.model_by_id else None

    @classmethod
    def get_model_copy_by_id(cls, id):
        """
        Suppose we use few model instances of same id, and we must be able to update
        them independently on root model updated. For this we should use not
        get_model_by_id(), but get_model_copy_by_id().
        :param id:
        :return:
        """
        model = cls.get_model_by_id(id)
        return model.copy() if model else None

    parent_model = None
    derived_models = None

    @property
    def is_available(self):
        return not self.is_marked_deleted and (not self.is_marked_for_delete or self.is_available_if_deleting)

    # Should be deleted on the first opportunity
    # ("Deleted" means removed from the list or set is_marked_deleted=True)
    _is_marked_for_delete = False

    @property
    def is_marked_for_delete(self):
        if self.parent_model and self.parent_model.is_marked_for_delete:
            return True
        return self._is_marked_for_delete

    @is_marked_for_delete.setter
    def is_marked_for_delete(self, value):
        self._is_marked_for_delete = value

    is_marked_deleted = False

    _id = None

    @property
    def id(self):
        return getattr(self, self.id_name) if self.id_name != "id" else self._id

    @id.setter
    def id(self, value):
        self._id = value

    def __init__(self, initial_config=None):
        # todo add to unittests
        initial_config = self.resolve_info(initial_config)
        super().__init__(initial_config)

        self.derived_models = []

        self.is_change_on_command = False
        self.on_reload(initial_config)
        del self.is_change_on_command

    def dispose(self):
        if self.parent_model:
            if self in self.parent_model.derived_models:
                self.parent_model.derived_models.remove(self)
            self.parent_model = None
        if self.derived_models:
            # (list() needed to make a copy)
            for model in list(self.derived_models):
                model.dispose()
            self.derived_models.clear()

    def on_reload(self, new_initial_config=None):
        """
        On initial data reloaded, do updates.
        :param new_initial_config:
        :return:
        """

        if not new_initial_config:
            return

        new_initial_config = self.resolve_info(new_initial_config)
        # For reset()
        # self._initial_config = new_initial_config
        self._check_id_changed(new_initial_config, self.id_name)
        self._check_id_changed(new_initial_config, "id")
        object_util.set_up_object(self._initial_config, new_initial_config, self._property_names)
        # For apply_changes() if is_change_on_command==True
        self.import_data(new_initial_config)

    # todo unittest
    def _check_id_changed(self, new_initial_config, id_name):
        prev_id = self.id

        if isinstance(new_initial_config, list):
            index = self._property_names.index(id_name)
            id_name = index if index < len(new_initial_config) else None
        elif id_name not in new_initial_config:
            id_name = None
        current_id = new_initial_config[id_name] if id_name else None

        if prev_id is not None and prev_id != "" and current_id is not None and prev_id != current_id:
            self.logging.error("Model's id is not supposed to be changed, but it changed!"
                               " prev_id: %s current_id: %s for %s", prev_id, current_id, self.__class__)
            # (Prevent changing id)
            new_initial_config[id_name] = None

    def copy(self):
        if self.parent_model:
            # Avoiding big trees (more than one level)!
            # (The normal is when one super contains several derived models which could not be super models themselves)
            return self.parent_model.copy()

        model = self.__class__(self._initial_config)
        # (Apply changes different of initial_config)
        object_util.set_up_object(model, self, self._property_names)

        model.parent_model = self
        self.derived_models.append(model)
        return model

    def import_data(self, data):
        super().import_data(data)

        # Important when is_change_on_command=True: super model could be reloaded
        # in any time, but all derived models should be update only when it's possible
        # (between games, or when room becomes empty). In proper circumstances
        # derived_model.apply_changes() will be called.
        for model in self.derived_models:
            model.import_data(data)

    # Utility

    def get_info_by_id(self, id=None):
        return object_util.get_info_by_id(self._info_by_id, id, self._property_names)

    def resolve_info(self, info):
        return object_util.resolve_info(self._info_by_id, info, self._property_names)


class ReloadableMultiModel(ReloadableModel):
    """
    Model as a composition of other models of same type.
    To compose a model by combining different models.

    For example, we have special config for Hold'em and Omaha poker,
    and also for Sit'n'go and Fast game. With this class we can easily
    create Hold'em + Sit'n'go, Omaha + Sit'n'go, Hold'em + Fast, Omaha + Fast
    config models.
    """

    use_copies_for_sub_models = True

    @classmethod
    def create_multimodel_by_ids(cls, ids):
        model_factory = cls.model_class or cls
        model = model_factory(ids=ids)
        # model.add_sub_models([cls.get_model_by_id(id) for id in ids])
        return model

    # @classmethod
    # def get_multimodel_copy_by_ids(cls, ids):
    #     # Note: all overlapping properties will be overwritten from first ids to last
    #     model_factory = cls.model_class or cls
    #     model = model_factory(*ids)
    #     # model.add_sub_models([cls.get_model_copy_by_id(id) for id in ids])
    #     return model

    _is_changed = False

    @property
    def is_changed(self):
        return self._is_changed or super().is_changed or \
               any([sub_model.is_changed for sub_model in self._sub_models])
    # ???
    # @property
    # def id(self):
    #     return None

    _ids = None

    @property
    def ids(self):
        return self._ids

    @ids.setter
    def ids(self, value):
        if self._ids != value:
            self._ids = value
            # (Note: if previous sub_models are copies, hove external references and
            #  could cause memory leaks, they should be disposed)
            self._sub_models = list(filter(None, [self.get_model_copy_by_id(id)
                                                  if self.use_copies_for_sub_models else self.get_model_by_id(id)
                                                  for id in self._ids])) if self._ids else []
            # if self.is_change_on_command:
            #     self._is_changed = True
            # else:
            #     self.apply_changes()
            self._is_changed = True
            if not self.is_change_on_command:
                self.apply_changes()

    def __init__(self, initial_config=None, ids=None):
        self._sub_models = []

        # (Set all default values before this)
        self.defaults = {}
        object_util.set_up_object(self.defaults, self, self._config_property_names)

        super().__init__(initial_config)

        # (Must be after _sub_models)
        self.ids = ids

        if self.is_change_on_command:
            self.apply_changes()

    def dispose(self):
        self.ids = None
        super().dispose()

    # def add_sub_models(self, sub_models):
    #     sub_models = sub_models if hasattr(sub_models, "__iter__") else [sub_models]
    #     for sub_model in sub_models:
    #         self._sub_models.append(sub_model)
    #         # Merge initial_configs
    #         object_util.set_up_object(self._initial_config, sub_model._initial_config, self._property_names)
    #     self._apply_initial_config()

    def apply_changes(self):
        # self._initial_config = {}
        id = self.id
        # Apply changes for each sub model this model consists of
        for sub_model in self._sub_models:
            # if sub_model.is_available and (self.is_changed or sub_model.is_changed):
            if sub_model.is_available:
                # # For sub_models on_reload()
                # object_util.set_up_object(self._initial_config, sub_model._initial_config, self._property_names)

                sub_model.apply_changes()
                # (_config_property_names doesn't contain "_changes_queue". Skipping defaults
                # needed not to override properties with default values of the last sub_model)
                object_util.set_up_object(self, sub_model, self._config_property_names,
                                          defaults_to_skip=sub_model.defaults)
                self.change_time = time.time()
        self.id = id

        self._is_changed = False
        super().apply_changes()

    def reset(self):
        object_util.set_up_object(self, self.defaults, self._config_property_names)

        super().reset()

        # ?
        for sub_model in self._sub_models:
            sub_model.reset()

        # Apply sub_models on the model
        self._is_changed = True  # To apply sub_models after their reset
        self.apply_changes()

    def copy(self):
        model = super().copy()
        model.ids = self.ids
        return model
