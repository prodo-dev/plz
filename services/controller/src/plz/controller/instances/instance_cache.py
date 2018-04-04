import multiprocessing
from typing import Callable, Dict, Optional

import collections.abc

from plz.controller.instances.instance_base import Instance


class InstanceCache(collections.abc.MutableMapping):
    """
    Because Gunicorn spawns a new subprocess per worker, we can't just store
    useful information in dictionaries. We need to share the data across
    processes. However, `Instance` objects can't be pickled, so we store the
    IDs and recreate the cache for each worker.
    """

    multiprocessing_manager = multiprocessing.Manager()

    def __init__(self, create: Callable[[str], Optional[Instance]]):
        self.create = create
        self.ids: Dict[str, bool] = self.multiprocessing_manager.dict()
        self.cache: Dict[str, Instance] = {}
        self.lock = multiprocessing.RLock()

    def __contains__(self, key):
        return key in self.ids

    def __getitem__(self, key):
        try:
            return self.cache[key]
        except KeyError:
            return self.__missing__(key)

    def __missing__(self, key):
        with self.lock:
            value = self.create(key)
            if value:
                self.__setitem__(key, value)
                return value

    def __setitem__(self, key, value):
        with self.lock:
            self.ids[key] = True
            self.cache[key] = value

    def __delitem__(self, key):
        with self.lock:
            del self.ids[key]
            del self.cache[key]

    def __iter__(self):
        return iter(self.ids)

    def __len__(self):
        return len(self.ids)

    def keys(self):
        return self.ids.keys()
