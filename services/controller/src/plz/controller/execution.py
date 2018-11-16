from abc import ABC, abstractmethod
from typing import Dict, Set, Optional, Any

from plz.controller.api.exceptions import ExecutionNotFoundException
from plz.controller.execution_metadata import convert_measures_to_dict
from plz.controller.instances.instance_base import InstanceProvider
from plz.controller.results import ResultsStorage
from plz.controller.results.results_base import Results


class Execution(ABC):
    def __init__(self, results: Results):
        self.results = results
        self.get_logs = self.results.get_logs
        self.get_output_files_tarball = self.results.get_output_files_tarball
        self.get_status = self.results.get_status

    def get_measures(self) -> dict:
        return convert_measures_to_dict(
            self.results.get_measures_files_tarball())

    def get_metadata(self) -> dict:
        stored_metadata = self.results.get_stored_metadata()
        # Measures are written by the workers in a specific directory and
        # we store the tarball as to preserve the original data as much as
        # possible. We don't store a structured representation as to avoid
        # having two sources of truth. Instead, we recompute the structured
        # representation from the tarball and add it to the metadata each time
        # it's requested.
        stored_metadata.update({'measures': self.get_measures()})
        return stored_metadata


class Executions:
    def __init__(self, results_storage: ResultsStorage,
                 instance_provider: InstanceProvider):
        self.results_storage = results_storage
        self.instance_provider = instance_provider

    def get(self, execution_id: str):
        with self.results_storage.get(execution_id) as results:
            # We acquire the lock to make sure the results were successfully
            # written. On return, the lock will be released but we know that,
            # after written, the content of the results doesn't change
            if results:
                return _FinishedExecution(results)

        instance = self.instance_provider.instance_for(execution_id)
        if instance is None:
            raise ExecutionNotFoundException(execution_id=execution_id)
        return _OngoingExecution(instance)


class _OngoingExecution(Execution):
    def __init__(self, instance):
        super().__init__(instance)


class _FinishedExecution(Execution):
    def __init__(self, results):
        super().__init__(results)


class Composition(ABC):
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


class AtomicComposition(Composition):
    """
    An atomic execution. Something was actually run, no sub-executions
    """
    def __init__(self, execution_id: str):
        super().__init__(execution_id)

    def to_jsonable_dict(self):
        return {'execution_id': self.execution_id}


class IndicesComposition(Composition):
    """
    Comprises several executions, each one processing a set of indices
    """
    def __init__(
            self, execution_id: str,
            indices_to_compositions: Dict[int, Optional[Composition]],
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
