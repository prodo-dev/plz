import os
from typing import Iterator

from plz.controller.results.results_base import ResultsStorage, untar


class LocalResultsStorage(ResultsStorage):
    def __init__(self, directory):
        self.directory = directory

    def publish_output(self,
                       execution_id: str,
                       output_tarball: Iterator[bytes]):
        output_directory = os.path.join(self.directory, execution_id, 'output')
        consume(untar(output_tarball, output_directory))


def consume(iterator):
    for _ in iterator:
        pass
