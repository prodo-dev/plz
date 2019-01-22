import json
import logging
import os
import shutil
from typing import Any, ContextManager, Iterator, Optional, Tuple

from redis import StrictRedis
from redis.lock import Lock

from plz.controller.arbitrary_object_json_encoder import dumps_arbitrary_json
from plz.controller.containers import Containers
from plz.controller.db_storage import DBStorage
from plz.controller.api.exceptions import AbortedExecutionException, \
    NotImplementedControllerException
from plz.controller.execution_composition import InstanceComposition, \
    subdir_name_for_index
from plz.controller.execution_metadata import compile_metadata_for_storage
from plz.controller.results.results_base import InstanceStatus, \
    InstanceStatusFailure, InstanceStatusSuccess, Results, ResultsContext, \
    ResultsStorage

log = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB


class LocalResultsStorage(ResultsStorage):
    def __init__(self,
                 redis: StrictRedis,
                 db_storage: DBStorage,
                 directory: str):
        super().__init__(db_storage)
        self.redis = redis
        self.db_storage = db_storage
        self.directory = directory

    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                containers: Containers,
                finish_timestamp: int):
        paths = Paths(self.directory, execution_id)
        with self._lock(execution_id):
            log.debug(f'Checking if results exist for {execution_id}')
            if os.path.exists(paths.finished_file):
                return

            log.debug(f'Creating dir for results of {execution_id}')
            _force_mk_empty_dir(paths.directory)

            with open(paths.exit_status, 'w') as f:
                print(exit_status, file=f)

            log.debug(f'Writing logs and output for {execution_id}')
            write_bytes(paths.logs, logs)
            metadata = compile_metadata_for_storage(
                self.db_storage.retrieve_start_metadata(execution_id),
                finish_timestamp)
            index_range_to_run = metadata['execution_spec'].get(
                'index_range_to_run')

            _write_output_and_measures(paths, containers, execution_id,
                                       index_range_to_run)

            with open(paths.metadata, 'w') as metadata_file:
                json.dump(metadata, metadata_file)
            with open(paths.finished_file, 'w') as _:  # noqa: F841 (unused)
                pass
            log.debug(f'Storing the execution id {execution_id} as finished')
            self.db_storage.add_finished_execution_id(
                user=metadata['user'], project=metadata['project'],
                execution_id=execution_id)

    def write_tombstone(self, execution_id: str, tombstone: object) -> None:
        paths = Paths(self.directory, execution_id)
        with self._lock(execution_id):
            if os.path.exists(paths.finished_file):
                return
            _force_mk_empty_dir(paths.directory)
            tombstone_json = dumps_arbitrary_json(tombstone)
            with open(paths.tombstone_file, 'w') as tombstone_file:
                tombstone_file.write(tombstone_json)
            with open(paths.finished_file, 'w') as _:  # noqa: F841 (unused)
                pass

    def get(self, execution_id: str) -> ContextManager[Optional[Results]]:
        paths = Paths(self.directory, execution_id)
        return LocalResultsContext(paths, self._lock(execution_id))

    def _lock(self, execution_id: str):
        lock_name = f'lock:{__name__}.{self.__class__.__name__}:{execution_id}'
        lock = self.redis.lock(lock_name)
        return lock

    def is_finished(self, execution_id: str):
        paths = Paths(self.directory, execution_id)
        return os.path.exists(paths.finished_file)


class LocalResultsContext(ResultsContext):
    def __init__(self, paths: 'Paths', lock: Lock):
        self.paths = paths
        self.lock = lock

    def __enter__(self):
        self.lock.acquire()
        if os.path.exists(self.paths.finished_file):
            if os.path.exists(self.paths.tombstone_file):
                return LocalTombstone(self.paths)
            else:
                return LocalResults(self.paths)
        else:
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()


class LocalResults(Results):
    def __init__(self, paths: 'Paths'):
        self.paths = paths

    def get_status(self) -> InstanceStatus:
        with open(self.paths.exit_status) as f:
            status = int(f.read())
        if status == 0:
            return InstanceStatusSuccess()
        else:
            return InstanceStatusFailure(status)

    def get_logs(self, since: Optional[int] = None, stdout: bool = True,
                 stderr: bool = True) -> Iterator[bytes]:
        return read_bytes(self.paths.logs)

    def get_output_files_tarball(self, path: Optional[str],
                                 index: Optional[int]) -> Iterator[bytes]:
        if path is not None:
            raise NotImplementedControllerException(
                'Getting paths of already finished executions is not '
                'implemented yet. Sorry about that')
        return read_bytes(self.paths.output(subdir_name_for_index(index)))

    def get_measures_files_tarball(self, index: Optional[int]) \
            -> Iterator[bytes]:
        return read_bytes(self.paths.measures(subdir_name_for_index(index)))

    def get_stored_metadata(self) -> dict:
        with open(self.paths.metadata, 'r') as metadata_file:
            return json.load(metadata_file)


class LocalTombstone(Results):
    def __init__(self, paths: 'Paths'):
        self.paths = paths

    def _raise_aborted(self) -> Any:
        with open(self.paths.tombstone_file, 'r') as tombstone:
            tombstone_object = json.load(tombstone)
        raise AbortedExecutionException(tombstone_object)

    def get_status(self) -> InstanceStatus:
        return self._raise_aborted()

    def get_logs(self, since: Optional[int] = None, stdout: bool = True,
                 stderr: bool = True) -> Iterator[bytes]:
        # In the future we might, for instance, store partial logs from the
        # workers. For now, a tombstone just raises exceptions
        return self._raise_aborted()

    def get_output_files_tarball(
            self, path: Optional[str], index: Optional[int]) \
            -> Iterator[bytes]:
        return self._raise_aborted()

    def get_measures_files_tarball(
            self, index: Optional[int]) -> Iterator[bytes]:
        return self._raise_aborted()

    def get_stored_metadata(self) -> dict:
        return self._raise_aborted()


class Paths:
    def __init__(self, base_dir, execution_id):
        if execution_id == '':
            raise ValueError(
                'Execution ID is empty when trying to publish results')
        self.directory = os.path.join(base_dir, execution_id)
        self.finished_file = os.path.join(self.directory, '.finished')
        self.tombstone_file = os.path.join(self.directory, '.tombstone')
        self.exit_status = os.path.join(self.directory, 'status')
        self.logs = os.path.join(self.directory, 'logs')
        self.metadata = os.path.join(self.directory, 'metadata.json')

    def output(self, subdir: Optional[str]) -> str:
        return os.path.join(
            self.directory,
            subdir if subdir is not None else '',
            'output.tar')

    def measures(self, subdir: Optional[str]) -> str:
        return os.path.join(
            self.directory,
            subdir if subdir is not None else '',
            'measures.tar')


def read_bytes(path: str) -> Iterator[bytes]:
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk


def write_bytes(path: str, chunks: Iterator[bytes]):
    with open(path, 'wb') as f:
        for chunk in chunks:
            f.write(chunk)


def _force_mk_empty_dir(directory: str):
    try:
        os.makedirs(directory)
    except OSError:
        shutil.rmtree(directory)
        os.makedirs(directory)


def _write_output_and_measures(paths: Paths, containers: Containers,
                               execution_id: str,
                               index_range_to_run: Optional[Tuple[int, int]]):
    ic = InstanceComposition.create_for(index_range_to_run)
    paths_and_getters = [
        (paths.output, ic.get_output_dirs_and_tarballs),
        (paths.measures, ic.get_measures_dirs_and_tarballs)
    ]
    for path_function, tarball_getter in paths_and_getters:
        dirs_and_tarballs = tarball_getter(
            execution_id=execution_id, containers=containers)
        for d, tarball in dirs_and_tarballs:
            dirname = os.path.dirname(path_function(d))
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            write_bytes(path_function(d), tarball)
