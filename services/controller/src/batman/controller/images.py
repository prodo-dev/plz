import base64
import boto3
import collections
import docker
import json
import time

from requests.exceptions import ConnectionError
from typing import BinaryIO, Iterator


Metadata = collections.namedtuple('Metadata', ['user', 'project', 'timestamp'])


class Images:
    DOCKER_REPOSITORY = \
        '024444204267.dkr.ecr.eu-west-1.amazonaws.com/batman/builds'

    @staticmethod
    def from_config(config):
        ecr_client = boto3.client('ecr')
        docker_api_client = docker.APIClient(base_url=config.docker_host)
        return Images(docker_api_client, ecr_client, config.aws_project)

    def __init__(self,
                 docker_api_client: docker.APIClient,
                 ecr_client,
                 aws_project: str):
        self.docker_api_client = docker_api_client
        self.ecr_client = ecr_client
        self.aws_project = aws_project

    def for_host(self, docker_url: str) -> 'Images':
        new_docker_api_client = docker.APIClient(base_url=docker_url)
        return Images(new_docker_api_client, self.ecr_client, self.aws_project)

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
        return self.docker_api_client.build(
            fileobj=fileobj,
            custom_context=True,
            encoding='bz2',
            rm=True,
            tag=f'{self.DOCKER_REPOSITORY}:{tag}')

    def push(self, tag: str):
        self.docker_api_client.push(
            self.DOCKER_REPOSITORY, tag,
            auth_config=self._aws_ecr_credentials())

    def pull(self, tag: str):
        self.docker_api_client.pull(
            self.DOCKER_REPOSITORY, tag,
            auth_config=self._aws_ecr_credentials())

    def can_pull(self):
        try:
            self.docker_api_client.pull('hello-world')
            return True
        except ConnectionError:
            return False

    @staticmethod
    def parse_metadata(json_string: str) -> Metadata:
        data = json.loads(json_string)
        timestamp = str(int(time.time() * 1000))
        return Metadata(data['user'], data['project'], timestamp)

    @staticmethod
    def construct_tag(metadata_string: str) -> str:
        metadata = Images.parse_metadata(metadata_string)
        return f'{metadata.user}-{metadata.project}-{metadata.timestamp}'

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
