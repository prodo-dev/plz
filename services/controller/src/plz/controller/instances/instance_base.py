import time
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Dict, Iterator, List, Optional, Tuple

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
    def dispose(self) -> str:
        pass

    @abstractmethod
    def get_idle_since_timestamp(
            self, container_state: Optional[ContainerState]=None) -> int:
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
            idle_since_timestamp=
            self.get_idle_since_timestamp(container_state),
            max_idle_seconds=self.get_max_idle_seconds())


class InstanceProvider(ABC):
    @abstractmethod
    def acquire_instance(
            self, execution_id: str, execution_spec: dict) -> Iterator[str]:
        pass

    @abstractmethod
    def release_instance(
            self, execution_id: str, idle_since_timestamp: Optional[int]=None):
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def push(self, image_tag: str):
        pass

    @abstractmethod
    def execution_id_and_instance_iterator(self) -> Iterator[Tuple[str, Instance]]:
        pass

    def tidy_up(self):
        now = int(time.time())
        for execution_id, instance in self.execution_id_and_instance_iterator():
            # TODO(sergio): move to this code to the instance
            ei = instance.get_execution_info()
            if execution_id == '':
                status = 'idle'
            else:
                status = ei.status

            if status != 'exited' and status != 'idle':
                return

            if status == 'exited':
                self.release_instance(execution_id, ei.idle_since_timestamp)
            # In weird cases just dispose as well
            if now - ei.idle_since_timestamp > ei.max_idle_seconds or \
                    ei.idle_since_timestamp > now or \
                    ei.max_idle_seconds < 0:
                instance.dispose()

    def get_commands(self) -> [ExecutionInfo]:
        return [
            instance.get_execution_info()
            for _, instance in self.execution_id_and_instance_iterator()]
