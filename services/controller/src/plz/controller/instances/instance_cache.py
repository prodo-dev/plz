import threading
from abc import ABC, abstractmethod
from typing import Dict, Iterator, Optional

import collections.abc

from plz.controller.instances.instance_base import Instance


class InstanceCache(collections.abc.MutableMapping, ABC):
    """
    Because Gunicorn spawns a new process per worker, we can't just store
    useful information in dictionaries. We need to keep it externally, and
    cache information per-process.
    """

    def __init__(self):
        self.cache: Dict[str, Instance] = {}
        self.lock = threading.RLock()

    @abstractmethod
    def find_instance(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def instance_exists(self, execution_id: str) -> bool:
        pass

    @abstractmethod
    def list_instances(self) -> Iterator[Instance]:
        pass

    def __contains__(self, key):
        with self.lock:
            value = self.instance_exists(key)
            self[key] = value
            return bool(value)

    def __getitem__(self, key):
        with self.lock:
            try:
                return self.cache[key]
            except KeyError:
                value = self.find_instance(key)
                self[key] = value
                return value

    def __setitem__(self, key, value):
        with self.lock:
            if value:
                self.cache[key] = value
            else:
                del self[key]

    def __delitem__(self, key):
        with self.lock:
            try:
                del self.cache[key]
            except KeyError:
                pass

    def __iter__(self):
        return self.list_instances()

    def __len__(self):
        """
        This is necessary to implement `MutableMapping`.
        :return: a useless number (probably 0)
        """
        return len(self.cache)

    def keys(self):
        return self.ids.keys()
