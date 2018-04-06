import hashlib
import os
import tarfile
import tempfile
from abc import ABC, abstractmethod

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.operation import check_status

READ_BUFFER_SIZE = 16384


class InputData(ABC):
    @staticmethod
    def from_configuration(configuration: Configuration):
        if not configuration.input:
            return NoInputData(configuration)
        if configuration.input.startswith('file://'):
            path = configuration.input[len('file://'):]
            return LocalInputData(configuration, path)
        raise CLIException('Could not parse the configured input.')

    def __init__(self, configuration: Configuration):
        self.prefix = f'http://{configuration.host}:{configuration.port}'

    def url(self, *path_segments: str):
        return self.prefix + '/' + '/'.join(path_segments)

    @abstractmethod
    def __enter__(self):
        pass

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @abstractmethod
    def publish(self) -> str:
        pass


class NoInputData(InputData):
    def __init__(self, configuration: Configuration):
        super().__init__(configuration)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def publish(self):
        pass


class LocalInputData(InputData):
    def __init__(self, configuration: Configuration, path: str):
        super().__init__(configuration)
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.tarball.close()

    def publish(self):
        input_id = self._compute_input_id()
        if not self._has_input(input_id):
            self._put_tarball(input_id)
        return input_id

    def _compute_input_id(self):
        file_hash = hashlib.sha256()
        self.tarball.seek(0)
        while True:
            data = self.tarball.read(READ_BUFFER_SIZE)
            if not data:
                break
            file_hash.update(data)
        return file_hash.hexdigest()

    def _has_input(self, input_id: str):
        response = requests.head(self.url('data', 'input', input_id))
        return response.status_code == requests.codes.ok

    def _put_tarball(self, input_id: str):
        self.tarball.seek(0)
        response = requests.put(self.url('data', 'input', input_id),
                                data=self.tarball,
                                stream=True)
        check_status(response, requests.codes.ok)
        return response.json()['id']
