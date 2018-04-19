from typing import Optional

import redis


class RedisRLock(object):
    def __init__(self, redis_client: redis.StrictRedis, name: str, **kwargs):
        self.lock = redis_client.lock(name, **kwargs)

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

    def acquire(self,
                blocking: Optional[bool] = None,
                blocking_timeout: Optional[float] = None):
        return self.lock.acquire(
            blocking=blocking,
            blocking_timeout=blocking_timeout)

    def release(self):
        self.lock.release()
