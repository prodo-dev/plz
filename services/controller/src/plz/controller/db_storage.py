import logging
from abc import ABC, abstractmethod
from typing import Optional, Set

from plz.controller.execution_composition import ExecutionComposition

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
    def add_finished_execution_id(self,
                                  user: str,
                                  project: str,
                                  execution_id: str) -> None:
        pass

    @abstractmethod
    def retrieve_finished_execution_ids(self,
                                        user: str,
                                        project: str) -> Set[str]:
        pass

    @abstractmethod
    def store_execution_composition(self,
                                    execution_composition: ExecutionComposition
                                    ) -> None:
        pass

    @abstractmethod
    def retrieve_execution_composition(self, execution_id: str) \
            -> ExecutionComposition:
        pass

    @abstractmethod
    def retrieve_execution_id_from_parent_and_index(self,
                                                    execution_id: str,
                                                    index: int
                                                    ) -> Optional[str]:
        pass

    @abstractmethod
    def retrieve_tombstone_sub_execution_ids(self, execution_id: str) -> [str]:
        pass

    def get_user_of_execution(self, execution_id: str) -> str:
        return self.retrieve_start_metadata(execution_id)['user']
