import os
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, Dict, Iterator, Optional, Set, Tuple

from plz.controller.containers import Containers
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


def _dirname_for_index(original_dirname: str, index: int):
    return os.path.join(original_dirname, str(index))


class InstanceComposition(ABC):
    """Helpers for instances based on the composition they're running"""

    @abstractmethod
    def get_startup_config(self) -> WorkerStartupConfig:
        pass

    @abstractmethod
    def get_output_dirs_and_tarballs(
            self, execution_id: str, containers: Containers,
            output_path: Optional[str] = None) \
            -> [(Optional[str], Iterator[bytes])]:
        pass

    @abstractmethod
    def get_measures_dirs_and_tarballs(
            self, execution_id: str, containers: Containers) \
            -> [(Optional[str], Iterator[bytes])]:
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
            VolumeEmptyDirectory(Volumes.OUTPUT_DIRECTORY),
            VolumeEmptyDirectory(Volumes.MEASURES_DIRECTORY)
        ]
        return WorkerStartupConfig(
            config_keys=config_keys,
            volumes=volumes)

    def get_output_dirs_and_tarballs(
            self, execution_id: str, containers: Containers,
            output_path: Optional[str] = None) \
            -> [(Optional[str], Iterator[bytes])]:
        tarball = containers.get_files(
            execution_id,
            os.path.join(
                Volumes.OUTPUT_DIRECTORY_PATH,
                output_path if output_path is not None else ''))
        directory = None
        return [(directory, tarball)]

    def get_measures_dirs_and_tarballs(
            self, execution_id: str, containers: Containers) \
            -> [(Optional[str], Iterator[bytes])]:
        tarball = containers.get_files(
            execution_id,
            Volumes.MEASURES_DIRECTORY_PATH)
        directory = None
        return [(directory, tarball)]


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
                i: _dirname_for_index(name_map[kind], i)
                for i in indices_to_run
            }
            for kind in name_map
        }
        config_keys.update({
            'index_to_summary_measures_path': os.path.join(
                _dirname_for_index(Volumes.MEASURES_DIRECTORY_PATH, i),
                'summary')
            for i in indices_to_run
        })
        config_keys.update({
            'indices': {'range': self.range_index_to_run}
        })
        volumes = [
            VolumeEmptyDirectory(
                _dirname_for_index(directory_path, i))
            for i in indices_to_run
            for directory_path in [
                Volumes.OUTPUT_DIRECTORY,
                Volumes.MEASURES_DIRECTORY
            ]
        ]
        return WorkerStartupConfig(
            config_keys=config_keys,
            volumes=volumes)

    def get_output_dirs_and_tarballs(
            self, execution_id: str, containers: Containers,
            output_path: Optional[str] = None) \
            -> [(Optional[str], Iterator[bytes])]:
        output_dirs_and_tarballs = []
        indices_to_run = range(*self.range_index_to_run)
        for i in indices_to_run:
            tarball = containers.get_files(
                execution_id,
                os.path.join(
                    _dirname_for_index(Volumes.OUTPUT_DIRECTORY_PATH, i),
                    output_path if output_path is not None else ''))
            directory = str(i)
            output_dirs_and_tarballs.append((directory, tarball))
        return output_dirs_and_tarballs

    def get_measures_dirs_and_tarballs(
            self, execution_id: str, containers: Containers) \
            -> [(Optional[str], Iterator[bytes])]:
        measures_dirs_and_tarballs = []
        indices_to_run = range(*self.range_index_to_run)
        for i in indices_to_run:
            tarball = containers.get_files(
                execution_id,
                _dirname_for_index(Volumes.MEASURES_DIRECTORY_PATH, i)
            )
            directory = str(i)
            measures_dirs_and_tarballs.append((directory, tarball))
        return measures_dirs_and_tarballs
