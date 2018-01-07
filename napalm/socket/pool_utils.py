import time


class DeferredDisposePool:
    """
    not used

    This pool can store instances for some time and dispose them
    on timeout if they were not used again during this period.
    This is convenient for restoring player's session after disconnect,
    for example.
    """

    DISPOSE_OLD_IN_TIMEOUT_SEC = 100
    # True for Player, False for User
    is_multiinstance_by_key = False
    # Player, User
    # inst_class should have dispose() method
    inst_class = None
    # "access_token"
    key_name = ""

    @property
    def instance_count(self):
        return len(self._inst_by_key)

    @property
    def total_instance_count(self):
        return len(self._inst_by_key) + len(self._inst_by_removetime)

    @property
    def instance_list(self):
        return self._inst_by_key.values()

    def __init__(self):
        self._inst_by_key = {}
        self._inst_get_count_by_key = {}
        self._inst_by_removetime = {}
        self._removetime_list = []

    def dispose(self):
        print("#(Pool.dispose)")
        for inst in self._inst_by_key:
            inst.dispose()
        for inst in self._inst_by_removetime:
            inst.dispose()

        self._inst_by_key = {}
        self._inst_get_count_by_key = {}
        self._inst_by_removetime = {}
        self._removetime_list = []

    # key_name="access_token"
    def get_or_create_instance(self, key):
        if not key or not self.key_name:
            return None

        result = None
        # Try to get currently using instance
        if not self.is_multiinstance_by_key and key in self._inst_by_key:
            result = self._inst_by_key[key]

        # Try to get instance from removed ones
        if not result:
            for remove_time, inst in self._inst_by_removetime.items():
                if key == getattr(inst, self.key_name):
                    del self._inst_by_removetime[remove_time]
                    self._removetime_list.remove(remove_time)
                    result = inst
                    print("#(Pool.get_or_create) got in pool by key:", key, result)
                    break

        # Create new otherwise
        if not result and self.inst_class:
            result = self.inst_class()
            setattr(result, self.key_name, key)
            print("#(Pool.get_or_create) create new inst:", result)

        # Save in dict by key
        if self.is_multiinstance_by_key:
            if key not in self._inst_by_key:
                self._inst_by_key[key] = []
            self._inst_by_key[key].append(result)
        else:
            self._inst_by_key[key] = result
        print("#TEMP(Pool.add) key:", key, "inst:", result, "self._inst_by_key[key]:", self._inst_by_key[key])

        # Increment use-count to avoid disposing an instance when
        # it's been using in another place by the same time
        if key not in self._inst_get_count_by_key:
            self._inst_get_count_by_key[key] = 0
        self._inst_get_count_by_key[key] += 1

        if self._inst_get_count_by_key[key] > 1:
            print("#(Pool.get_or_create) use-count:", self._inst_get_count_by_key[key], "key:", key, "inst:", result)

        return result

    def remove(self, inst, dispose=False):
        if not inst or not self.key_name:
            return None

        self._check_remove_by_timeout()

        key = getattr(inst, self.key_name)

        # To remove an instance remove() method should be called so many times
        # as get_or_create() was called for the same key
        if key in self._inst_get_count_by_key:
            self._inst_get_count_by_key[key] -= 1
            if self._inst_get_count_by_key[key] > 0:
                print("#(Pool.remove) use-count:", self._inst_get_count_by_key[key], "key:", key, "inst:", inst)
                return None

        print("#TEMP(Pool.remove) key:", key, "inst:", inst, "self._inst_by_key[key]:", self._inst_by_key[key])
        # Remove from dict by key
        if key in self._inst_by_key:
            if self.is_multiinstance_by_key:
                self._inst_by_key[key].remove(inst)
            else:
                del self._inst_by_key[key]

        remove_time = None
        if dispose:
            # Immediate dispose
            inst.dispose()
        else:
            # Deferred dispose on timeout
            remove_time = time.time()
            while remove_time in self._inst_by_removetime:
                remove_time += 1
            self._inst_by_removetime[remove_time] = inst
            self._removetime_list.append(remove_time)

        print("#(Pool.remove) key:", key, "inst:", inst, "insts count:", len(self._inst_by_key),
              "insts-in-pool:", len(self._inst_by_removetime), "remove_time:", remove_time, "dispose:", dispose)
        return inst

    def _check_remove_by_timeout(self):
        current_time = time.time()
        remove_count = 0
        for remove_time in self._removetime_list:
            if current_time - remove_time < self.DISPOSE_OLD_IN_TIMEOUT_SEC:
                break

            # Dispose inst by timeout
            inst = self._inst_by_removetime[remove_time]
            if inst:
                print("# (Pool._check_remove_by_timeout) dispose inst for:", getattr(inst, self.key_name))
                inst.dispose()
            del self._inst_by_removetime[remove_time]

            remove_count += 1

        if remove_count:
            self._removetime_list = self._removetime_list[remove_count:]
            print("#(Pool._check_remove_by_timeout) insts-in-pool:", len(self._removetime_list), "==",
                  len(self._inst_by_removetime))
