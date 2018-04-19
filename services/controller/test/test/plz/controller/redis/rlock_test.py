import random
import unittest

import redis
import time

from plz.controller.redis.rlock import RedisRLock


class RedisRLockTest(unittest.TestCase):
    def setUp(self):
        self.redis = redis.StrictRedis()

    def test_acquires_and_releases(self):
        lock = RedisRLock(self.redis, self._random_lock_name())
        lock.acquire()
        locked = True
        lock.release()
        self.assertTrue(locked)

    def test_acts_as_a_context_manager(self):
        lock = RedisRLock(self.redis, self._random_lock_name())
        with lock:
            locked = True
        self.assertTrue(locked)

    def test_releasing_without_acquiring_fails(self):
        lock = RedisRLock(self.redis, self._random_lock_name())
        with self.assertRaises(redis.exceptions.LockError) as cm:
            lock.release()
        self.assertEqual(cm.exception.args,
                         ('Cannot release an unlocked lock',))

    def test_locks_can_time_out(self):
        lock = RedisRLock(self.redis, self._random_lock_name(), timeout=0.1)
        with self.assertRaises(redis.exceptions.LockError) as cm:
            with lock:
                time.sleep(0.2)
        self.assertEqual(cm.exception.args,
                         ("Cannot release a lock that's no longer owned",))

    def test_cannot_acquire_two_locks_with_the_same_name(self):
        lock_name = self._random_lock_name()
        lock_1 = RedisRLock(self.redis, lock_name)
        lock_2 = RedisRLock(self.redis, lock_name)
        with lock_1:
            acquired = lock_2.acquire(blocking_timeout=0.1)
        self.assertFalse(acquired)

    def test_can_acquire_two_locks_with_different_names(self):
        lock_1 = RedisRLock(self.redis, self._random_lock_name())
        lock_2 = RedisRLock(self.redis, self._random_lock_name())
        with lock_1:
            with lock_2:
                locked = True
        self.assertTrue(locked)

    def _random_lock_name(self):
        lock_name = \
            f'lock:{__name__}' \
            f'.{self.__class__.__name__}' \
            f'#{random.randint(0, 65536)}'
        self.addCleanup(self._delete_lock, lock_name)
        return lock_name

    def _delete_lock(self, lock_name):
        del self.redis[lock_name]
