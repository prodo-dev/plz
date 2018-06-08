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
                measures_tarball: Iterator[bytes],
                finish_timestamp: int):
        pass

    @abstractmethod
    def get(self, execution_id: str) -> ContextManager[Optional['Results']]:
        pass

    @abstractmethod
    def is_finished(self, execution_id: str):
        pass


class Results(ABC):
    @abstractmethod
    def get_status(self) -> 'InstanceStatus':
        pass

    @abstractmethod
    def get_logs(self, since: Optional[int] = None, stdout: bool = True,
                 stderr: bool = True) -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_output_files_tarball(self) -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_measures_files_tarball(self) -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_stored_metadata(self) -> dict:
        pass


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


ResultsContext = ContextManager[Optional[Results]]


class CouldNotGetOutputException(Exception):
    pass
