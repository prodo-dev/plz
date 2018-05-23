import base64
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile
from abc import ABC, abstractmethod
from json import JSONDecodeError
from typing import ContextManager, Iterator, Optional, Tuple, IO

from werkzeug.contrib.iterio import IterIO

from plz.controller.db_storage import DBStorage

log = logging.getLogger(__name__)


class ResultsStorage(ABC):
    def __init__(self, db_storage: DBStorage):
        self.db_storage = db_storage

    @abstractmethod
    def publish(self,
                execution_id: str,
                exit_status: int,
                logs: Iterator[bytes],
                output_tarball: Iterator[bytes],
                measures_tarball: Iterator[bytes],
                finish_timestamp: int):
        pass

    @abstractmethod
    def get(self, execution_id: str) -> ContextManager[Optional['Results']]:
        pass

    @abstractmethod
    def is_finished(self, execution_id: str):
        pass


class Results:
    @abstractmethod
    def status(self) -> int:
        pass

    @abstractmethod
    def logs(self) -> Iterator[bytes]:
        pass

    @abstractmethod
    def output_tarball(self) -> Iterator[bytes]:
        pass

    @abstractmethod
    def measures(self) -> dict:
        pass

    @abstractmethod
    def metadata(self) -> Iterator[bytes]:
        pass


ResultsContext = ContextManager[Optional[Results]]


def compile_metadata(
        db_storage: DBStorage, execution_id: str, finish_timestamp: int,
        measures_tarball: Iterator[bytes]):
    start_metadata = db_storage.retrieve_start_metadata(execution_id)
    return {**start_metadata,
            'measures': convert_measures_to_dict(measures_tarball),
            'finish_timestamp': finish_timestamp}


def convert_measures_to_dict(measures_tarball: Iterator[bytes]) -> dict:
    measures_dict = {}
    for path, file_content in _tar_iterator(measures_tarball):
        content = file_content.read()
        content_as_json = None
        try:
            content_as_json = json.load(io.BytesIO(content))
        except JSONDecodeError or UnicodeDecodeError:
            pass
        if content_as_json is not None:
            measures_dict[path] = content_as_json
        else:
            measures_dict[path] = {
                'base64_bytes': base64.encodebytes(content).decode('ascii')
            }
    return measures_dict


def _tar_iterator(tarball_bytes: Iterator[bytes]) \
        -> Iterator[Tuple[str, Optional[IO]]]:
    # The response is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        shutil.copyfileobj(IterIO(tarball_bytes), tarball)
        # And rewind to the start.
        tarball.seek(0)
        tar = tarfile.open(fileobj=tarball)
        for tarinfo in tar.getmembers():
            # Drop the first segment, because it's just the name of the
            # directory that was tarred up, and we don't care.
            path_segments = tarinfo.name.split(os.sep)[1:]
            if path_segments:
                # Unfortunately we can't just pass `*path_segments`
                # because `os.path.join` explicitly expects an argument
                # for the first parameter.
                path = os.path.join(path_segments[0], *path_segments[1:])
                file_bytes = tar.extractfile(tarinfo.name)
                # Not None for files and links
                if file_bytes is not None:
                    yield path, tar.extractfile(tarinfo.name)


class CouldNotGetOutputException(Exception):
    pass
