from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Set


class ExecutionComposition(ABC):
    """
    How is an execution composed?

    It can be an atomic execution, or it can consist of several executions
    each one processing different items, etc.
    """
    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    @abstractmethod
    def to_jsonable_dict(self) -> Any:
        """
        Create a dict that we can turn into json
        """
        pass


class AtomicComposition(ExecutionComposition):
    """
    An atomic execution. Something was actually run, no sub-executions
    """
    def __init__(self, execution_id: str):
        super().__init__(execution_id)

    def to_jsonable_dict(self):
        return {'execution_id': self.execution_id}


class IndicesComposition(ExecutionComposition):
    """
    Comprises several executions, each one processing a set of indices
    """
    def __init__(
            self, execution_id: str,
            indices_to_compositions: Dict[int, Optional[ExecutionComposition]],
            tombstone_execution_ids: Set[str]):
        super().__init__(execution_id)
        # A non-injective map with the sub-execution for a given index. If
        # there's no execution for a given index (for instance, it didn't
        # execute yet) the value is None
        self.indices_to_compositions = indices_to_compositions
        self.tombstone_execution_ids = tombstone_execution_ids

    def to_jsonable_dict(self):
        def jsonable_of_index(i: int):
            if self.indices_to_compositions[i] is None:
                return None
            return self.indices_to_compositions[i].to_jsonable_dict()

        return {
            'execution_id': self.execution_id,
            'indices_to_compositions': {
                i: jsonable_of_index(i)
                for i in self.indices_to_compositions
            },
            'tombstone_executions': list(self.tombstone_execution_ids)
        }
