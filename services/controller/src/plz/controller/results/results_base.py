from abc import ABC, abstractmethod
from typing import ContextManager, Iterator, Optional


class ResultsStorage(ABC):
    @abstractmethod
    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                output_tarball: Iterator[bytes]):
        pass

    @abstractmethod
    def get(self, execution_id: str) -> ContextManager[Optional['Results']]:
        pass


class Results:
    @abstractmethod
    def status(self) -> int:
        pass

    @abstractmethod
    def logs(self) -> Iterator[bytes]:
        pass

    @abstractmethod
    def output_tarball(self) -> Iterator[bytes]:
        pass


ResultsContext = ContextManager[Optional[Results]]
