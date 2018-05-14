import logging
from abc import ABC, abstractmethod
from typing import ContextManager, Iterator, Optional

from plz.controller.db_storage import DBStorage

log = logging.getLogger(__name__)


class ResultsStorage(ABC):
    def __init__(self, db_storage: DBStorage):
        self.db_storage = db_storage

    @abstractmethod
    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                output_tarball: Iterator[bytes],
                finish_timestamp: int):
        pass

    @abstractmethod
    def get(self, execution_id: str) -> ContextManager[Optional['Results']]:
        pass

    @abstractmethod
    def is_finished(self, execution_id: str):
        pass

    def compile_metadata(self, execution_id: str, finish_timestamp: int):
        start_metadata = self.db_storage.retrieve_start_metadata(execution_id)
        return {**start_metadata, 'finish_timestamp': finish_timestamp}


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

    @abstractmethod
    def metadata(self) -> Iterator[bytes]:
        pass


ResultsContext = ContextManager[Optional[Results]]


class CouldNotGetOutputException(Exception):
    pass
