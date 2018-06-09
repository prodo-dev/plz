import logging
from abc import ABC, abstractmethod
from typing import Set

log = logging.getLogger(__name__)


class DBStorage(ABC):
    @abstractmethod
    def store_start_metadata(self, execution_id: str, start_metadata: dict) \
            -> None:
        pass

    @abstractmethod
    def retrieve_start_metadata(self, execution_id: str) -> dict:
        pass

    @abstractmethod
    def add_finished_execution_id(
            self, user: str, project: str, execution_id: str) -> None:
        pass

    @abstractmethod
    def retrieve_finished_execution_ids(
            self, user: str, project: str) -> Set[str]:
        pass
