import io
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Dict, Iterator, List, Optional

from redis import StrictRedis

from plz.controller.containers import ContainerState
from plz.controller.results.results_base import ResultsStorage

Parameters = Dict[str, Any]
ExecutionInfo = namedtuple(
    'ExecutionInfo',
    ['execution_id', 'running', 'status', 'instance_type', 'max_idle_seconds',
     'idle_since_timestamp'])


class Instance(ABC):
    def __init__(self, redis: StrictRedis):
        self.redis = redis
        self._redis_lock = None

    @abstractmethod
    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO]):
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
    def logs(self, stdout: bool = True, stderr: bool = True) \
            -> Iterator[bytes]:
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
    def dispose(self) -> str:
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

    @abstractmethod
    def set_execution_id(self, execution_id: str, max_idle_seconds: int) \
            -> bool:
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
                _lock_held: bool=True):
        pass

    @property
    @abstractmethod
    def _instance_id(self):
        pass

    @property
    def _lock(self):
        if self._redis_lock is None:
            name = f'lock:{__name__}.{self.__class__.__name__}' + \
                   f'#_lock:{self._instance_id}'
            self._redis_lock = self.redis.lock(name)
        return self._redis_lock


class InstanceProvider(ABC):
    @abstractmethod
    def acquire_instance(
            self, execution_id: str, execution_spec: dict) -> Iterator[Dict]:
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def stop_execution(self, execution_id: str):
        pass

    @abstractmethod
    def release_instance(
            self, execution_id: str,
            idle_since_timestamp: Optional[int] = None):
        pass

    @abstractmethod
    def push(self, image_tag: str):
        pass

    @abstractmethod
    def instance_iterator(self) -> Iterator[Instance]:
        pass

    def harvest(self):
        for instance in self.instance_iterator():
            info = instance.get_execution_info()
            if info.status == 'exited':
                self.release_instance(
                    info.execution_id, info.idle_since_timestamp)
            instance.dispose_if_its_time(info)

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
