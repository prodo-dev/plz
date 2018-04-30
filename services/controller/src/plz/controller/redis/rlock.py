import threading

import redis

# noinspection PyUnresolvedReferences, PyProtectedMember
_RLock = threading._PyRLock


class RedisRLock:
    """
    Behaviour broadly copied from ``threading._PyRLock``.
    """

    def __init__(self, redis_client: redis.StrictRedis, name: str, **kwargs):
        self._lock = redis_client.lock(name, **kwargs)
        self._count = 0

    def __repr__(self):
        return "<%s %s.%s object count=%d at %s>" % (
            "locked" if self._lock.locked() else "unlocked",
            self.__class__.__module__,
            self.__class__.__qualname__,
            self._count,
            hex(id(self))
        )

    def acquire(self, blocking=None, timeout=None):
        """Acquire a lock, blocking or non-blocking.

        When invoked without arguments: if this object already owns the
        lock, increment the recursion level by one, and return immediately.
        Otherwise, if another object owns the lock, block until the lock is
        unlocked. Once the lock is unlocked, then grab ownership, set the
        recursion level to one, and return. If more than one object is
        blocked waiting until the lock is unlocked, only one at a time will
        be able to grab ownership of the lock. There is no return value in
        this case.

        When invoked with the blocking argument set to true, do the same thing
        as when called without arguments, and return true.

        When invoked with the blocking argument set to false, do not block.
        If a call without an argument would block, return false immediately;
        otherwise, do the same thing as when called without arguments,
        and return true.

        When invoked with the floating-point timeout argument set to a
        positive value, block for at most the number of seconds specified by
        timeout and as long as the lock cannot be acquired.  Return true if
        the lock has been acquired, false if the timeout has elapsed.
        """
        if self._count:
            self._count += 1
            return 1
        rc = self._lock.acquire(blocking, timeout)
        if rc:
            self._count = 1
        return rc

    __enter__ = acquire

    def release(self):
        """Release a lock, decrementing the recursion level.

        If after the decrement it is zero, reset the lock to unlocked (not
        owned by any thread), and if any other threads are blocked waiting
        for the lock to become unlocked, allow exactly one of them to
        proceed. If after the decrement the recursion level is still
        nonzero, the lock remains locked and owned by the calling thread.

        Only call this method when the calling thread owns the lock. A
        RuntimeError is raised if this method is called when the lock is
        unlocked.

        There is no return value.

        """
        if not self._count:
            raise RuntimeError("cannot release un-acquired lock")
        self._count = count = self._count - 1
        if not count:
            self._lock.release()

    def __exit__(self, t, v, tb):
        self.release()

    # Internal methods used by condition variables

    def _acquire_restore(self, state):
        self._lock.acquire()
        self._count = state

    def _release_save(self):
        if self._count == 0:
            raise RuntimeError("cannot release un-acquired lock")
        count = self._count
        self._count = 0
        self._lock.release()
        return count

    def _is_owned(self):
        # Return True if lock is owned by current_thread.
        # This method is called only if _lock doesn't have _is_owned().
        if self._lock.acquire(0):
            self._lock.release()
            return False
        else:
            return True
