import os
import shutil
from typing import Iterator

from redis import StrictRedis

from plz.controller.results.results_base import ResultsStorage, untar


class LocalResultsStorage(ResultsStorage):
    def __init__(self, redis: StrictRedis, directory: str):
        self.redis = redis
        self.directory = directory

    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                output_tarball: Iterator[bytes]):
        lock_name = f'lock:{__name__}.{self.__class__.__name__}:{execution_id}'
        with self.redis.lock(lock_name):
            directory = os.path.join(self.directory, execution_id)
            finished_file = os.path.join(directory, '.finished')
            exit_status_path = os.path.join(directory, 'status')
            logs_path = os.path.join(directory, 'logs')
            output_directory = os.path.join(directory, 'output')

            if os.path.exists(finished_file):
                return

            try:
                os.makedirs(directory)
            except OSError:
                shutil.rmtree(directory)
                os.makedirs(directory)

            with open(exit_status_path, 'w') as f:
                print(exit_status, file=f)

            with open(logs_path, 'wb') as f:
                for line in logs:
                    f.write(line)

            consume(untar(output_tarball, output_directory))

            with open(finished_file, 'w') as _:
                pass


def consume(iterator):
    for _ in iterator:
        pass
