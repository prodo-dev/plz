import collections
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator

import docker

from plz.controller.exceptions import JSONResponseException

Metadata = collections.namedtuple('Metadata', ['user', 'project', 'timestamp'])

log = logging.getLogger(__name__)


class Images(ABC):
    def __init__(self, docker_api_client: docker.APIClient, repository: str):
        self.docker_api_client = docker_api_client
        self.repository = repository

    @staticmethod
    def construct_tag(metadata_string: str) -> str:
        metadata = Images.parse_metadata(metadata_string)
        return f'{metadata.user}-{metadata.project}-{metadata.timestamp}'

    @staticmethod
    def parse_metadata(json_string: str) -> Metadata:
        data = json.loads(json_string)
        timestamp = str(int(time.time() * 1000))
        return Metadata(data['user'], data['project'], timestamp)

    @abstractmethod
    def for_host(self, docker_url: str) -> 'Images':
        pass

    @abstractmethod
    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[bytes]:
        pass

    @abstractmethod
    def push(self, tag: str):
        pass

    @abstractmethod
    def pull(self, tag: str):
        pass

    @abstractmethod
    def can_pull(self, times: int) -> bool:
        pass

    def _build(self, fileobj: BinaryIO, tag: str) -> Iterator[bytes]:
        builder = self.docker_api_client.build(
            fileobj=fileobj,
            custom_context=True,
            encoding='bz2',
            rm=True,
            tag=f'{self.repository}:{tag}')
        for message_bytes in builder:
            try:
                message_str = message_bytes.decode('utf-8').strip()
                message_json = json.loads(message_str)
                # Ignore progress indicators because they're too noisy
                if 'progress' not in message_json:
                    log.debug('Build: ' + message_str)
                self._raise_on_error_in_json(message_str, message_json)
            except UnicodeDecodeError:
                pass
            except json.JSONDecodeError:
                pass
            yield message_bytes

    @staticmethod
    def _raise_on_error_in_json(message_str: str, message_json: dict):
        if 'error' in message_json:
            raise ImageBuildError(message_str)


class ImageBuildError(JSONResponseException):
    pass
