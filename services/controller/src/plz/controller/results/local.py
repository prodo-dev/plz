import os
from typing import Iterator

from plz.controller.results.results_base import ResultsStorage, untar


class LocalResultsStorage(ResultsStorage):
    def __init__(self, directory):
        self.directory = directory

    def publish_output(self,
                       execution_id: str,
                       exit_status: int,
                       logs: Iterator[bytes],
                       output_tarball: Iterator[bytes]):
        directory = os.path.join(self.directory, execution_id)
        os.makedirs(directory, exist_ok=True)

        exit_status_path = os.path.join(directory, 'status')
        with open(exit_status_path, 'w') as f:
            print(exit_status, file=f)

        logs_path = os.path.join(directory, 'logs')
        with open(logs_path, 'wb') as f:
            for line in logs:
                f.write(line)

        output_directory = os.path.join(directory, 'output')
        consume(untar(output_tarball, output_directory))


def consume(iterator):
    for _ in iterator:
        pass
