from abc import ABC

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
            raise ExecutionNotFound(execution_id=execution_id)
        return _OngoingExecution(instance)


class ExecutionNotFound(Exception):
    def __init__(self, execution_id):
        self.execution_id = execution_id


class _OngoingExecution(Execution):
    def __init__(self, instance):
        super().__init__(instance)


class _FinishedExecution(Execution):
    def __init__(self, results):
        super().__init__(results)
