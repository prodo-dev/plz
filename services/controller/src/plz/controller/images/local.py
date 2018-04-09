from typing import BinaryIO, Iterator

import docker

from plz.controller.images.images_base import Images


class LocalImages(Images):
    def __init__(self, docker_api_client: docker.APIClient, repository: str):
        self.docker_api_client = docker_api_client
        self.repository = repository

    def build(self, fileobj: BinaryIO, tag: str) -> Iterator[str]:
        return self.docker_api_client.build(
            fileobj=fileobj,
            custom_context=True,
            encoding='bz2',
            rm=True,
            tag=f'{self.repository}:{tag}')

    def for_host(self, docker_url: str) -> 'LocalImages':
        new_docker_api_client = docker.APIClient(base_url=docker_url)
        return LocalImages(new_docker_api_client, self.repository)

    def push(self, tag: str):
        pass

    def pull(self, tag: str):
        pass

    def can_pull(self):
        pass
