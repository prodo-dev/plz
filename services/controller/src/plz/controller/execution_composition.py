import os
from abc import ABC, abstractmethod
from collections import namedtuple, defaultdict
from typing import Any, Callable, Dict, Iterator, Optional, Set, Tuple

from plz.controller.containers import Containers
from plz.controller.execution_metadata import enrich_start_metadata
from plz.controller.volumes import VolumeEmptyDirectory, Volumes


class ExecutionComposition(ABC):
    """
    How is an execution composed?

    It can be an atomic execution, or it can consist of several executions
    each one processing different items, etc.
    """

    def __init__(self, execution_id: str):
        self.execution_id = execution_id

    @staticmethod
    def from_parallel_indices_range(
            parallel_indices_range: Optional[Tuple[int, int]],
            execution_id: str) -> 'ExecutionComposition':
        if parallel_indices_range is None:
            return AtomicComposition(execution_id)
        else:
            return IndicesComposition(
                execution_id,
                indices_to_compositions=None,
                tombstone_execution_ids=None)

    @abstractmethod
    def to_jsonable_dict(self) -> Any:
        """
        Create a dict that we can turn into json
        """
        pass

    @abstractmethod
    def create_metadatas_for_all_executions(
                self, command: [str], snapshot_id: str, parameters: dict,
                instance_market_spec: dict, execution_spec: dict,
                start_metadata: dict,
                parallel_indices_range: Optional[Tuple[int, int]],
                indices_per_execution: Optional[int],
                previous_execution_id: Optional[str],
                execution_id: str,
                execution_id_generator: Callable[[], str]) -> [dict]:
        pass

    @abstractmethod
    def get_component_brief_description(self, metadata: dict) -> str:
        pass


class AtomicComposition(ExecutionComposition):
    """
    An atomic execution. Something was actually run, no sub-executions
    """

    def __init__(self, execution_id: str):
        super().__init__(execution_id)

    def to_jsonable_dict(self):
        return {'execution_id': self.execution_id}

    def create_metadatas_for_all_executions(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            parallel_indices_range: Optional[Tuple[int, int]],
            indices_per_execution: Optional[int],
            previous_execution_id: Optional[str],
            execution_id: str,
            execution_id_generator: Callable[[], str]) -> [dict]:
        enriched_start_metadata = enrich_start_metadata(
            execution_id, start_metadata, command, snapshot_id, parameters,
            instance_market_spec, execution_spec, parallel_indices_range,
            index_range_to_run=None,
            indices_per_execution=indices_per_execution,
            previous_execution_id=previous_execution_id)
        return [enriched_start_metadata]

    def get_component_brief_description(self, metadata: dict) -> str:
        return ''


class IndicesComposition(ExecutionComposition):
    """
    Comprises several executions, each one processing a set of indices
    """

    def __init__(
            self, execution_id: str,
            indices_to_compositions: Optional[
                Dict[int, Optional[ExecutionComposition]]],
            tombstone_execution_ids: Optional[Set[str]]):
        super().__init__(execution_id)
        # A non-injective map with the sub-execution for a given index. If
        # there's no execution for a given index (for instance, it didn't
        # execute yet) the value is None
        self.indices_to_compositions = indices_to_compositions \
            if indices_to_compositions is not None \
            else defaultdict(lambda: None)
        self.tombstone_execution_ids = tombstone_execution_ids \
            if tombstone_execution_ids is not None \
            else {}

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

    def create_metadatas_for_all_executions(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            parallel_indices_range: Optional[Tuple[int, int]],
            indices_per_execution: Optional[int],
            previous_execution_id: Optional[str],
            execution_id: str,
            execution_id_generator: Callable[[], str]) -> [dict]:
        enriched_start_metadata = enrich_start_metadata(
            execution_id, start_metadata, command, snapshot_id, parameters,
            instance_market_spec, execution_spec, parallel_indices_range,
            index_range_to_run=None,
            indices_per_execution=indices_per_execution,
            previous_execution_id=previous_execution_id)
        metadatas = [enriched_start_metadata]
        if indices_per_execution is None:
            indices_per_execution = 1
        for i in range(parallel_indices_range[0],
                       parallel_indices_range[1],
                       indices_per_execution):
            this_exec_n_indices = min(
                indices_per_execution,
                parallel_indices_range[1] - parallel_indices_range[0] - i)
            subexecution_id = execution_id_generator()
            for j in range(this_exec_n_indices):
                self.assign_index(i + j,
                                  AtomicComposition(subexecution_id))
            enriched_start_metadata = enrich_start_metadata(
                subexecution_id,
                start_metadata, command, snapshot_id, parameters,
                instance_market_spec, execution_spec,
                parallel_indices_range=None,
                index_range_to_run=(i, i + this_exec_n_indices),
                indices_per_execution=None,
                previous_execution_id=None)
            metadatas.append(enriched_start_metadata)
        return metadatas

    def assign_index(
            self, index: int, execution_composition: ExecutionComposition) \
            -> None:
        self.indices_to_compositions[index] = execution_composition

    def get_component_brief_description(self, metadata: dict) -> str:
        return 'Indices: ' + (', '.join(
            str(n) for n in range(*metadata['index_range_to_run'])))


WorkerStartupConfig = namedtuple(
    'WorkerStartupConfig',
    ['config_keys', 'volumes'])


def subdir_name_for_index(index: int) -> Optional[str]:
    if index is None:
        return None
    return str(index)


def _dirname_for_index(original_dirname: str, index: int):
    subdir = subdir_name_for_index(index)
    return os.path.join(original_dirname, subdir if subdir is not None else '')


class InstanceComposition(ABC):
    """Helpers for instances based on the composition they're running"""

    @staticmethod
    def create_for(index_range_to_run: Optional[Tuple[int, int]]) \
            -> 'InstanceComposition':
        if index_range_to_run is None:
            return AtomicInstanceComposition()
        return IndicesInstanceComposition(index_range_to_run)

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

    @abstractmethod
    def compose_measures(
            self, measures_from_index: Callable[[Optional[int]], dict]) \
            -> dict:
        pass

    @staticmethod
    def get_output_tarball(containers: Containers, execution_id: str,
                           index: Optional[int], output_path: Optional[str]) \
            -> Iterator[bytes]:
        output_path = output_path if output_path is not None else ''
        if index is not None:
            return containers.get_files(
                execution_id,
                os.path.join(
                    _dirname_for_index(Volumes.OUTPUT_DIRECTORY_PATH, index),
                    output_path))
        else:
            return containers.get_files(
                execution_id,
                os.path.join(Volumes.OUTPUT_DIRECTORY_PATH, output_path))

    @staticmethod
    def get_measures_tarball(
            containers: Containers, execution_id: str, index: Optional[int]) \
            -> Iterator[bytes]:
        if index is not None:
            return containers.get_files(
                execution_id,
                _dirname_for_index(Volumes.MEASURES_DIRECTORY_PATH, index)
            )
        else:
            return containers.get_files(
                execution_id,
                Volumes.MEASURES_DIRECTORY_PATH)


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
        tarball = InstanceComposition.get_output_tarball(
            containers, execution_id, index=None, output_path=output_path)
        directory = None
        return [(directory, tarball)]

    def get_measures_dirs_and_tarballs(
            self, execution_id: str, containers: Containers) \
            -> [(Optional[str], Iterator[bytes])]:
        tarball = InstanceComposition.get_measures_tarball(
            containers, execution_id, index=None)
        directory = None
        return [(directory, tarball)]

    def compose_measures(
            self, measures_from_index: Callable[[Optional[int]], dict]) \
            -> dict:
        # index is None
        return measures_from_index(None)


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
            'index_to_summary_measures_path': {
                i: os.path.join(
                    _dirname_for_index(Volumes.MEASURES_DIRECTORY_PATH, i),
                    'summary')
                for i in indices_to_run
            }
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
        for index in indices_to_run:
            tarball = InstanceComposition.get_output_tarball(
                containers, execution_id, index, output_path)
            directory = subdir_name_for_index(index)
            output_dirs_and_tarballs.append((directory, tarball))
        return output_dirs_and_tarballs

    def get_measures_dirs_and_tarballs(
            self, execution_id: str, containers: Containers) \
            -> [(Optional[str], Iterator[bytes])]:
        measures_dirs_and_tarballs = []
        indices_to_run = range(*self.range_index_to_run)
        for index in indices_to_run:
            tarball = InstanceComposition.get_measures_tarball(
                containers, execution_id, index)
            directory = subdir_name_for_index(index)
            measures_dirs_and_tarballs.append((directory, tarball))
        return measures_dirs_and_tarballs

    def compose_measures(
            self, measures_from_index: Callable[[Optional[int]], dict]) \
            -> dict:
        return {
            index: measures_from_index(index)
            for index in range(*self.range_index_to_run)
        }
