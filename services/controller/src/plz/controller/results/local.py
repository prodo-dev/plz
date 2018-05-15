import json
import os
import shutil
from typing import ContextManager, Iterator, Optional

from redis import StrictRedis
from redis.lock import Lock

from plz.controller.db_storage import DBStorage
from plz.controller.results.results_base \
    import Results, ResultsContext, ResultsStorage, compile_metadata

LOCK_TIMEOUT = 60  # 1 minute
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
                output_tarball: Iterator[bytes],
                finish_timestamp: int):
        paths = Paths(self.directory, execution_id)
        with self._lock(execution_id):
            if os.path.exists(paths.finished_file):
                return

            try:
                os.makedirs(paths.directory)
            except OSError:
                shutil.rmtree(paths.directory)
                os.makedirs(paths.directory)

            with open(paths.exit_status, 'w') as f:
                print(exit_status, file=f)

            write_bytes(paths.logs, logs)
            write_bytes(paths.output, output_tarball)
            with open(paths.metadata, 'w') as metadata_file:
                json.dump(compile_metadata(
                            self.db_storage, execution_id, finish_timestamp),
                          metadata_file)
            with open(paths.finished_file, 'w') as _:  # noqa: F841 (unused)
                pass

    def get(self, execution_id: str) -> ContextManager[Optional[Results]]:
        paths = Paths(self.directory, execution_id)
        return LocalResultsContext(paths, self._lock(execution_id))

    def _lock(self, execution_id: str):
        lock_name = f'lock:{__name__}.{self.__class__.__name__}:{execution_id}'
        lock = self.redis.lock(lock_name, timeout=LOCK_TIMEOUT)
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
            return LocalResults(self.paths)
        else:
            return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()


class LocalResults(Results):
    def __init__(self, paths: 'Paths'):
        self.paths = paths

    def status(self) -> int:
        with open(self.paths.exit_status) as f:
            return int(f.read())

    def logs(self) -> Iterator[bytes]:
        return read_bytes(self.paths.logs)

    def output_tarball(self) -> Iterator[bytes]:
        return read_bytes(self.paths.output)

    def metadata(self) -> Iterator[bytes]:
        return read_bytes(self.paths.metadata)


class Paths:
    def __init__(self, *segments):
        self.directory = os.path.join(*segments)
        self.finished_file = os.path.join(self.directory, '.finished')
        self.exit_status = os.path.join(self.directory, 'status')
        self.logs = os.path.join(self.directory, 'logs')
        self.output = os.path.join(self.directory, 'output.tar')
        self.metadata = os.path.join(self.directory, 'metadata.json')


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
