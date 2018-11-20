import os
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Dict, Optional, Set, Tuple

from plz.controller.volumes import VolumeEmptyDirectory, Volumes


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


WorkerStartupConfig = namedtuple(
    'WorkerStartupConfig',
    ['config_keys', 'volumes'])


class InstanceComposition(ABC):
    """Helpers for instances based on the composition they're running"""

    @abstractmethod
    def get_startup_config(self) -> WorkerStartupConfig:
        pass

    @staticmethod
    def create_for(index_range_to_run: Optional[Tuple[int, int]]) \
            -> 'InstanceComposition':
        if index_range_to_run is None:
            return AtomicInstanceComposition()
        return IndicesInstanceComposition(index_range_to_run)


class AtomicInstanceComposition(InstanceComposition):
    def get_startup_config(self) -> WorkerStartupConfig:
        config_keys = {
            'output_directory': Volumes.OUTPUT_DIRECTORY_PATH,
            'measures_directory': Volumes.MEASURES_DIRECTORY_PATH,
            'summary_measures_path': os.path.join(
                Volumes.MEASURES_DIRECTORY_PATH, 'summary')
        }
        volumes = [
            VolumeEmptyDirectory(Volumes.OUTPUT_DIRECTORY_PATH),
            VolumeEmptyDirectory(Volumes.MEASURES_DIRECTORY_PATH)
        ]
        return WorkerStartupConfig(
            config_keys=config_keys,
            volumes=volumes)


class IndicesInstanceComposition(InstanceComposition):
    def __init__(self, range_index_to_run: Optional[Tuple[int, int]]):
        self.range_index_to_run = range_index_to_run

    def get_startup_config(self) -> WorkerStartupConfig:
        indices_to_run = range(*self.range_index_to_run)
        name_map = {
            'measures': Volumes.MEASURES_DIRECTORY_PATH,
            'output': Volumes.OUTPUT_DIRECTORY_PATH
        }
        config_keys = {
            f'index_to_{kind}_directory': {
                i: os.path.join(name_map[kind], str(i))
                for i in indices_to_run
            }
            for kind in name_map
        }
        config_keys.update({
            'index_to_summary_measures_path': os.path.join(
                Volumes.MEASURES_DIRECTORY_PATH, str(i), 'summary')
            for i in indices_to_run
        })
        config_keys.update({
            'indices': {'range': self.range_index_to_run}
        })
        volumes = [
            VolumeEmptyDirectory(
                os.path.join(directory_path, str(i)))
            for i in indices_to_run
            for directory_path in [
                Volumes.OUTPUT_DIRECTORY_PATH,
                Volumes.MEASURES_DIRECTORY_PATH
            ]
        ]
        return WorkerStartupConfig(
            config_keys=config_keys,
            volumes=volumes)
