import io
import logging
import time
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, ContextManager, Dict, Iterator, List, Optional

from redis import StrictRedis
from redis.lock import Lock

from plz.controller.containers import ContainerMissingException, ContainerState
from plz.controller.results.results_base import ResultsStorage

log = logging.getLogger(__name__)

Parameters = Dict[str, Any]
ExecutionInfo = namedtuple(
    'ExecutionInfo',
    ['execution_id', 'running', 'status', 'instance_type', 'max_idle_seconds',
     'idle_since_timestamp'])


class Instance(ABC):
    def __init__(self, redis: StrictRedis):
        self.redis = redis
        # Need to create and memoised the lock afterwards, as we need the
        # AWS instance id and it's not available at this point. Use
        # _redis_lock to access it
        self._memoised_lock = None

    @abstractmethod
    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            docker_run_args: Dict[str, str]) -> None:
        pass

    def status(self) -> 'InstanceStatus':
        state = self.container_state()
        if not state:
            raise InstanceMissingStateException()
        if state.running:
            return InstanceStatusRunning()
        elif state.exit_code == 0:
            return InstanceStatusSuccess()
        else:
            return InstanceStatusFailure(state.exit_code)

    @abstractmethod
    def logs(self, since: Optional[int],
             stdout: bool = True, stderr: bool = True) -> Iterator[bytes]:
        pass

    @abstractmethod
    def output_files_tarball(self) -> Iterator[bytes]:
        pass

    def exit_status(self) -> int:
        status = self.status()
        if status.exit_status is None:
            raise InstanceStillRunningException(self.get_execution_id())
        return status.exit_status

    @abstractmethod
    def stop_execution(self):
        pass

    @abstractmethod
    def get_idle_since_timestamp(
            self, container_state: Optional[ContainerState] = None) -> int:
        pass

    @abstractmethod
    def get_execution_id(self) -> str:
        pass

    @abstractmethod
    def get_instance_type(self) -> str:
        pass

    @abstractmethod
    def get_max_idle_seconds(self) -> int:
        pass

    @abstractmethod
    def dispose_if_its_time(
            self, execution_info: Optional[ExecutionInfo] = None):
        # We happen to have the execution info at hand when calling it,
        # and getting the info is not free (queries to the docker server in the
        # workers), so we allow to pass the info as parameter
        pass

    def get_execution_info(self) -> ExecutionInfo:
        container_state = self.container_state()
        if container_state is None:
            running = False
            status = 'idle'
            idle_since_timestamp = self.get_idle_since_timestamp()
        else:
            running = container_state.running
            status = container_state.status
            idle_since_timestamp = self.get_idle_since_timestamp(
                container_state)
        return ExecutionInfo(
            instance_type=self.get_instance_type(),
            execution_id=self.get_execution_id(),
            running=running,
            status=status,
            idle_since_timestamp=idle_since_timestamp,
            max_idle_seconds=self.get_max_idle_seconds())

    @abstractmethod
    def container_state(self) -> Optional[ContainerState]:
        pass

    @abstractmethod
    def release(self, results_storage: ResultsStorage,
                idle_since_timestamp: int,
                release_container: bool = True,
                _lock_held: bool = False) -> bool:
        pass

    def harvest(self, results_storage: ResultsStorage):
        with self._lock:
            try:
                info = self.get_execution_info()
            except ContainerMissingException:
                # The container for an execution can't be found although
                # we have an instance for it. Release the instance without
                # trying to access the container
                log.exception(
                    f'Instance {self._instance_id} for execution id: '
                    f'{self.get_execution_id()} missing container')
                self.release(
                    results_storage,
                    idle_since_timestamp=int(time.time()),
                    # There's no container so don't try to release things
                    # there
                    release_container=False,
                    _lock_held=True)
                return
            if info.status == 'exited':
                self.release(
                    results_storage,
                    info.idle_since_timestamp,
                    _lock_held=True)

            if info.status in {'exited', 'idle'}:
                self.dispose_if_its_time(info)

    @property
    @abstractmethod
    def _instance_id(self):
        pass

    @property
    def _redis_lock(self) -> Lock:
        if self._memoised_lock is None:
            lock_name = f'lock:{__name__}.{self.__class__.__name__}' + \
                        f'#_lock:{self._instance_id}'
            self._memoised_lock = Lock(self.redis, lock_name)
        return self._memoised_lock

    @property
    def _lock(self):
        return _InstanceContextManager(self._redis_lock)


class InstanceProvider(ABC):
    def __init__(self, results_storage: ResultsStorage):
        self.results_storage = results_storage

    @abstractmethod
    def run_in_instance(self,
                        execution_id: str,
                        command: List[str],
                        snapshot_id: str,
                        parameters: Parameters,
                        input_stream: Optional[io.BytesIO],
                        execution_spec: dict,) -> Iterator[Dict[str, Any]]:
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def stop_execution(self, execution_id: str):
        pass

    def release_instance(
            self, execution_id: str,
            fail_if_not_found: bool=True,
            idle_since_timestamp: Optional[int]=None):
        instance = self.instance_for(execution_id)
        if instance is None:
            if fail_if_not_found:
                raise ValueError(f'Instance for Execution ID {execution_id} ' +
                                 'not found')
            else:
                return
        instance.release(self.results_storage, idle_since_timestamp)

    @abstractmethod
    def push(self, image_tag: str):
        pass

    @abstractmethod
    def instance_iterator(self) -> Iterator[Instance]:
        pass

    def harvest(self):
        for instance in self.instance_iterator():
            # noinspection PyBroadException
            try:
                instance.harvest(self.results_storage)
            except Exception:
                # Make sure that an exception thrown while harvesting an
                # instance doesn't stop the whole harvesting process
                log.exception('Exception harvesting')

    def get_executions(self) -> [ExecutionInfo]:
        return [
            instance.get_execution_info()
            for instance in self.instance_iterator()]


class InstanceStatus(ABC):
    def __init__(self,
                 running: bool,
                 success: Optional[bool],
                 exit_status: Optional[int]):
        self.running = running
        self.success = success
        self.exit_status = exit_status


class InstanceStatusRunning(InstanceStatus):
    def __init__(self):
        super().__init__(
            running=True,
            success=None,
            exit_status=None)


class InstanceStatusSuccess(InstanceStatus):
    def __init__(self):
        super().__init__(
            running=False,
            success=True,
            exit_status=0)


class InstanceStatusFailure(InstanceStatus):
    def __init__(self, exit_status: int):
        super().__init__(
            running=False,
            success=False,
            exit_status=exit_status)


class InstanceNotRunningException(Exception):
    pass


class InstanceStillRunningException(Exception):
    pass


class InstanceMissingStateException(Exception):
    pass


class _InstanceContextManager(ContextManager):
    """
    Allow for the lock to be acquired in several stack frames of the same
    thread
    """
    def __init__(self, instance_lock: Lock):
        self.instance_lock = instance_lock
        self.lock = None

    def acquire(self, blocking=None):
        if self.instance_lock.local.token is None:
            self.instance_lock.acquire(blocking=blocking)
            self.lock = self.instance_lock
        else:
            self.lock = None

    def release(self):
        if self.lock is not None:
            self.lock.release()

    def __enter__(self):
        self.acquire(blocking=True)

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
