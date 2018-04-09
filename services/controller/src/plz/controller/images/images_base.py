import collections
import json
import time
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator

Metadata = collections.namedtuple('Metadata', ['user', 'project', 'timestamp'])


class Images(ABC):
    def __init__(self, repository):
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
    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
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
