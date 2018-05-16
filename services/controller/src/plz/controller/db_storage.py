import logging
from abc import ABC, abstractmethod
from typing import Set

log = logging.getLogger(__name__)


class DBStorage(ABC):
    @abstractmethod
    def store_start_metadata(self, execution_id: str, start_metadata: dict) \
            -> None:
        pass

    def retrieve_start_metadata(self, execution_id: str) -> dict:
        pass

    def add_execution_id_for_user_and_project(
            self, user: str, project: str, execution_id: str) -> None:
        pass

    def retrieve_execution_ids_for_user_and_project(
            self, user: str, project: str) -> Set[str]:
        pass
