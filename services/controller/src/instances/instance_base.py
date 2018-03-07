from abc import ABC, abstractmethod
from typing import Iterator, List, Optional


class Instance(ABC):
    @abstractmethod
    def run(self, command: List[str], snapshot_id: str):
        pass

    @abstractmethod
    def logs(self, stdout: bool = True, stderr: bool = True):
        pass

    @abstractmethod
    def output(self):
        pass

    @abstractmethod
    def cleanup(self):
        pass


class InstanceProvider(ABC):
    @abstractmethod
    def acquire_instance(self, execution_id: str) -> Iterator[str]:
        pass

    @abstractmethod
    def release_instance(self, execution_id: str):
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    @abstractmethod
    def push(self, image_tag: str):
        pass
