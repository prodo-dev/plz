import os
import tarfile
import tempfile
from abc import ABC, abstractmethod
from typing import Callable, Optional

import requests

from plz.cli.exceptions import CLIException
from plz.cli.operation import check_status


class InputData(ABC):
    @staticmethod
    def from_string(input_string: Optional[str]):
        if not input_string:
            return NoInputData()
        if input_string.startswith('file://'):
            path = input_string[len('file://'):]
            return LocalInputData(path)
        raise CLIException('Could not parse the configured input.')

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def publish(self, url: Callable[..., str]) -> str:
        pass


class NoInputData(InputData):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def publish(self, url):
        pass


class LocalInputData(InputData):
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        files = (os.path.join(directory, file)
                 for directory, _, files in os.walk(self.path)
                 for file in files)
        self.tarball = tempfile.NamedTemporaryFile()
        with tarfile.open(self.tarball.name, mode='w:bz2') as tar:
            for file in files:
                with open(file, 'rb') as f:
                    stats = os.stat(file)
                    tarinfo = tarfile.TarInfo(name=self.path)
                    tarinfo.size = stats.st_size
                    tar.addfile(tarinfo, fileobj=f)
        self.tarball.seek(0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tarball.close()

    def publish(self, url):
        response = requests.post(url('data', 'input'),
                                 data=self.tarball,
                                 stream=True)
        check_status(response, requests.codes.ok)
        return response.json()['id']
