from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Dict, Iterator, List, Optional

from plz.controller.containers import ContainerState

Parameters = Dict[str, Any]
ExecutionInfo = namedtuple(
    'ExecutionInfo',
    ['execution_id', 'running', 'status', 'instance_type', 'max_idle_seconds',
     'idle_since_timestamp'])


class Instance(ABC):
    @abstractmethod
    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters):
        pass

    @abstractmethod
    def logs(self, stdout: bool = True, stderr: bool = True):
        pass

    @abstractmethod
    def output_files_tarball(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass

    @abstractmethod
    def get_container_state(self) -> Optional[ContainerState]:
        pass

    @abstractmethod
    def stop_command(self):
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

    def get_execution_info(self) -> ExecutionInfo:
        container_state = self.get_container_state()
        if container_state is None:
            container_state = ContainerState(
                running='False', status='idle',
                finished_at=self.get_idle_since_timestamp())
        return ExecutionInfo(
            instance_type=self.get_instance_type(),
            execution_id=self.get_execution_id(),
            running=container_state.running,
            status=container_state.status,
            idle_since_timestamp=self.get_idle_since_timestamp(
                container_state),
            max_idle_seconds=self.get_max_idle_seconds())


class InstanceProvider(ABC):
    @abstractmethod
    def acquire_instance(
            self, execution_id: str, execution_spec: dict) -> Iterator[str]:
        pass

    @abstractmethod
    def release_instance(
            self, execution_id: str,
            idle_since_timestamp: Optional[int] = None):
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def push(self, image_tag: str):
        pass

    @abstractmethod
    def instance_iterator(self) -> Iterator[Instance]:
        pass

    @abstractmethod
    def stop_command(self, execution_id: str):
        pass

    def tidy_up(self):
        for instance in self.instance_iterator():
            ei = instance.get_execution_info()
            if ei.status == 'exited':
                self.release_instance(
                    ei.execution_id, ei.idle_since_timestamp)
            instance.dispose_if_its_time(ei)

    def get_commands(self) -> [ExecutionInfo]:
        return [
            instance.get_execution_info()
            for instance in self.instance_iterator()]
