import random
import threading
import time
import unittest

import redis

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
        with self.assertRaises(RuntimeError) as cm:
            lock.release()
        self.assertEqual(cm.exception.args,
                         ('cannot release un-acquired lock',))

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
        lock_2 = RedisRLock(self.redis, lock_name, blocking_timeout=0.1)
        with lock_1:
            acquired = lock_2.acquire()
        self.assertFalse(acquired)

    def test_can_acquire_two_locks_with_different_names(self):
        lock_1 = RedisRLock(self.redis, self._random_lock_name())
        lock_2 = RedisRLock(self.redis, self._random_lock_name())
        with lock_1:
            with lock_2:
                locked = True
        self.assertTrue(locked)

    def test_can_enter_a_lock_multiple_times(self):
        lock = RedisRLock(
            self.redis, self._random_lock_name(), blocking_timeout=0.1)
        with lock:
            acquired = lock.acquire()
        self.assertTrue(acquired)

    def test_multiple_threads_can_share_a_lock_without_sharing_objects(self):
        lock_name = self._random_lock_name()
        self.counter = 0

        def something_requiring_locking():
            lock = RedisRLock(self.redis, lock_name)
            with lock:
                counter = self.counter
                time.sleep(random.randint(0, 10) / 100)  # between 0 and 0.1
                self.counter = counter + 1

        threads = [threading.Thread(target=something_requiring_locking)
                   for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(self.counter, 10)

    def test_multiple_threads_can_share_a_lock_object(self):
        self.lock = RedisRLock(self.redis, self._random_lock_name())
        self.counter = 0

        def something_requiring_locking():
            with self.lock:
                counter = self.counter
                time.sleep(random.randint(0, 10) / 100)  # between 0 and 0.1
                self.counter = counter + 1

        threads = [threading.Thread(target=something_requiring_locking)
                   for _ in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(self.counter, 10)

    def _random_lock_name(self):
        lock_name = \
            f'lock:{__name__}' \
            f'.{self.__class__.__name__}' \
            f'#{random.randint(0, 65536)}'
        self.addCleanup(self._delete_lock, lock_name)
        return lock_name

    def _delete_lock(self, lock_name):
        del self.redis[lock_name]
