import threading

import redis

# noinspection PyUnresolvedReferences, PyProtectedMember
_RLock = threading._PyRLock


class RedisRLock(_RLock):
    def __init__(self, redis_client: redis.StrictRedis, name: str, **kwargs):
        super().__init__()
        self._block = redis_client.lock(name, **kwargs)
