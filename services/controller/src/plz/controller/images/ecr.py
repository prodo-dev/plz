import base64
import json
import logging
import time
from typing import Any, BinaryIO, Callable, Iterator

import docker
from requests.exceptions import ChunkedEncodingError, ConnectionError

from plz.controller.images.images_base import Images

log = logging.getLogger(__name__)


class ECRImages(Images):
    def __init__(self,
                 docker_api_client_creator: Callable[[], docker.APIClient],
                 ecr_client_creator: Callable[[], Any],
                 registry: str,
                 repository: str,
                 login_validity_in_minutes: int):
        super().__init__(docker_api_client_creator, repository)
        self.registry = registry
        self.ecr_client_creator = ecr_client_creator
        self.ecr_client = self.ecr_client_creator()
        self.last_login_time = None
        self.login_validity_in_minutes = login_validity_in_minutes

    def for_host(self, docker_url: str) -> 'ECRImages':
        def new_docker_api_client_creator():
            return docker.APIClient(base_url=docker_url)
        return ECRImages(
            new_docker_api_client_creator,
            self.ecr_client,
            self.registry,
            self.repository,
            self.login_validity_in_minutes)

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
        if self.last_login_time:
            time_since_last_login = time.time() - self.last_login_time
            if time_since_last_login < self.login_validity_in_minutes * 60:
                log.debug('Skipping ECR login')
                return
        log.debug('Logging in to ECR')
        # Recreating the clients in each login, as otherwise over time we
        # start noticing weird authentication errors. The errors stop when
        # we restart the controller (without restarting the docker daemon)
        # which suggests that the problem is with the state of the (clients
        # of the) controller.
        self.docker_api_client = self.docker_api_client_creator()
        self.ecr_client = self.ecr_client_creator()
        authorization_token = self.ecr_client.get_authorization_token()
        authorization_data = authorization_token['authorizationData']
        encoded_token = authorization_data[0]['authorizationToken']
        token = base64.b64decode(encoded_token).decode('utf-8')
        username, password = token.split(':')
        self.docker_api_client.login(
            username=username,
            password=password,
            registry=self.registry)
        self.last_login_time = time.time()

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
