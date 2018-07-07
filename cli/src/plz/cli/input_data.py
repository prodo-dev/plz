import contextlib
import hashlib
import os
import tarfile
import tempfile
from abc import abstractmethod
from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.log import log_debug, log_info
from plz.controller.api import Controller
from plz.controller.api.types import InputMetadata

READ_BUFFER_SIZE = 16384


class InputData(contextlib.AbstractContextManager):
    @staticmethod
    def from_configuration(
            configuration: Configuration, controller: Controller):
        if not configuration.input:
            return NoInputData()
        if configuration.input.startswith('file://'):
            path = configuration.input[len('file://'):]
            return LocalInputData(
                controller=controller,
                user=configuration.user,
                project=configuration.project,
                path=path)
        raise CLIException('Could not parse the configured input.')

    @abstractmethod
    def publish(self) -> Optional[str]:
        pass


class NoInputData(InputData):
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def publish(self) -> Optional[str]:
        return None


class LocalInputData(InputData):
    def __init__(self,
                 controller: Controller,
                 user: str,
                 project: str,
                 path: str):
        self.controller = controller
        self.user = user
        self.project = project
        self.path = os.path.normpath(path)
        self.tarball = None
        self.input_id = None
        self._timestamp_millis = None

    def __enter__(self):
        input_metadata = InputMetadata.of(
            user=self.user,
            project=self.project,
            path=self.path,
            timestamp_millis=self.timestamp_millis)
        # Try to avoid building the tarball. Look at maximum modification
        # time in the input, and if we have in input for the timestamp, use
        # that one
        input_id = self.controller.get_input_id_or_none(input_metadata)
        log_debug(f'Input ID from the controller: {input_id}')
        if input_id:
            log_info('Input files not changed according to modification times')
            self.input_id = input_id
            return self

        log_debug('Building the tarball!')
        files = (os.path.join(directory, file)
                 for directory, _, files in os.walk(self.path)
                 for file in files)
        self.tarball = tempfile.NamedTemporaryFile()
        with tarfile.open(self.tarball.name, mode='w:bz2') as tar:
            for file in files:
                name = os.path.relpath(file, self.path)
                size = os.stat(file).st_size
                with open(file, 'rb') as f:
                    tarinfo = tarfile.TarInfo(name=name)
                    tarinfo.size = size
                    tar.addfile(tarinfo, fileobj=f)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.tarball:
            self.tarball.close()

    def publish(self) -> Optional[str]:
        # We asked the controller previously and found the data is there
        # with this input ID
        if self.input_id is not None:
            return self.input_id

        input_id = self._compute_input_id()
        if not self._has_input(input_id):
            log_info(f'{os.path.getsize(self.tarball.name)} input bytes to '
                     'upload')
            self._put_tarball(input_id)
        return input_id

    def _compute_input_id(self) -> str:
        file_hash = hashlib.sha256()
        self.tarball.seek(0)
        while True:
            data = self.tarball.read(READ_BUFFER_SIZE)
            if not data:
                break
            file_hash.update(data)
        return file_hash.hexdigest()

    def _has_input(self, input_id: str) -> bool:
        input_metadata = InputMetadata.of(
            user=self.user,
            project=self.project,
            path=self.path,
            timestamp_millis=self.timestamp_millis)
        return self.controller.check_input_data(input_id, input_metadata)

    def _put_tarball(self, input_id: str) -> None:
        self.tarball.seek(0)
        input_metadata = InputMetadata.of(
            user=self.user,
            project=self.project,
            path=self.path,
            timestamp_millis=self.timestamp_millis
        )
        self.controller.put_input(
            input_id=input_id,
            input_metadata=input_metadata,
            input_data_stream=self.tarball)

    @property
    def timestamp_millis(self) -> int:
        if self._timestamp_millis is None:
            modified_timestamps_in_seconds = [
                    os.path.getmtime(path[0]) for path in os.walk(self.path)]
            max_timestamp_in_seconds = max(
                    [0] + modified_timestamps_in_seconds)
            self._timestamp_millis = int(max_timestamp_in_seconds * 1000)
        return self._timestamp_millis
