import base64
import json
import logging
from typing import BinaryIO, Iterator

import docker
from requests.exceptions import ChunkedEncodingError, ConnectionError

from plz.controller.images.images_base import Images

log = logging.getLogger(__name__)


class ECRImages(Images):
    def __init__(self,
                 docker_api_client: docker.APIClient,
                 ecr_client,
                 registry: str,
                 repository: str):
        super().__init__(docker_api_client, repository)
        self.registry = registry
        self.ecr_client = ecr_client

    def for_host(self, docker_url: str) -> 'ECRImages':
        new_docker_api_client = docker.APIClient(base_url=docker_url)
        return ECRImages(
            new_docker_api_client,
            self.ecr_client,
            self.registry,
            self.repository)

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[bytes]:
        self._login()
        return self._build(fileobj, tag)

    def push(self, tag: str):
        self._login()
        self._log_output('Push', self.docker_api_client.push(
            repository=self.repository, tag=tag, stream=True))

    def pull(self, tag: str):
        self._login()
        self._log_output('Push', self.docker_api_client.pull(
            repository=self.repository, tag=tag, stream=True))

    def can_pull(self, times: int) -> bool:
        try:
            for _ in range(times):
                self.docker_api_client.pull('hello-world')
                log.debug('Could pull image')
            return True
        except (ChunkedEncodingError, ConnectionError):
            log.debug('Couldn\'t pull image')
            return False

    def _login(self) -> None:
        authorization_token = self.ecr_client.get_authorization_token()
        authorization_data = authorization_token['authorizationData']
        encoded_token = authorization_data[0]['authorizationToken']
        token = base64.b64decode(encoded_token).decode('utf-8')
        username, password = token.split(':')
        self.docker_api_client.login(
            username=username,
            password=password,
            registry=self.registry)

    @staticmethod
    def _log_output(label: str, stream: Iterator[bytes]):
        for message_bytes in stream:
            message_str = message_bytes.decode('utf-8').strip()
            try:
                message_json = json.loads(message_str)
                # Ignore progress indicators because they're too noisy
                if 'progress' not in message_json:
                    log.debug(f'{label}: {message_str}')
            except json.JSONDecodeError:
                log.debug(f'{label}: {message_str}')
