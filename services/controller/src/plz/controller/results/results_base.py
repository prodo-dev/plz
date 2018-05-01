import logging
from abc import ABC, abstractmethod
from typing import ContextManager, Iterator, Optional

log = logging.getLogger(__name__)


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

    @abstractmethod
    def is_finished(self, execution_id: str):
        pass

    def check_logs_available(self, execution_id: str) -> None:
        with self.get(execution_id) as results:
            if not results:
                raise CouldNotGetOutputException(
                    f'Couldn\'t read the results for {execution_id}')
            else:
                # Make sure the logs are non-empty
                try:
                    next(results.logs())
                except StopIteration:
                    raise CouldNotGetOutputException(
                        f'Suspicious empty logs for {execution_id}')
        log.debug(f'Logs are available for {execution_id}')


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


class CouldNotGetOutputException(Exception):
    pass
