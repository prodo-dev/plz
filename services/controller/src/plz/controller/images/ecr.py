import base64
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
                 repository: str):
        super().__init__(repository)
        self.docker_api_client = docker_api_client
        self.ecr_client = ecr_client

    def for_host(self, docker_url: str) -> 'ECRImages':
        new_docker_api_client = docker.APIClient(base_url=docker_url)
        return ECRImages(
            new_docker_api_client, self.ecr_client, self.repository)

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
        return self.docker_api_client.build(
            fileobj=fileobj,
            custom_context=True,
            encoding='bz2',
            rm=True,
            tag=f'{self.repository}:{tag}')

    def push(self, tag: str):
        for message in self.docker_api_client.push(
                repository=self.repository,
                tag=tag,
                auth_config=self._aws_ecr_credentials(),
                stream=True):
            log.debug('Push: ' + message.decode('utf-8').strip())

    def pull(self, tag: str):
        for message in self.docker_api_client.pull(
                repository=self.repository,
                tag=tag,
                auth_config=self._aws_ecr_credentials(),
                stream=True):
            log.debug('Pull: ' + message.decode('utf-8').strip())

    def can_pull(self, times: int) -> bool:
        try:
            for _ in range(times):
                self.docker_api_client.pull('hello-world')
                log.debug('Could pull image')
            return True
        except (ChunkedEncodingError, ConnectionError):
            log.debug('Couldn\'t pull image')
            return False

    def _aws_ecr_credentials(self) -> dict:
        authorization_token = self.ecr_client.get_authorization_token()
        authorization_data = authorization_token['authorizationData']
        encoded_token = authorization_data[0]['authorizationToken']
        token = base64.b64decode(encoded_token).decode('utf-8')
        username, password = token.split(':')
        return {
            'username': username,
            'password': password,
        }
