import logging
from typing import Iterator

import docker
import docker.errors

from images import Images


class Containers:
    log = logging.getLogger('containers')

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Containers(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def run(self, name: str, tag: str, command: str):
        image = f'{Images.DOCKER_REPOSITORY}:{tag}'
        container = self.docker_client.containers.run(
            image=image,
            command=command,
            name=name,
            detach=True,
        )
        self.log.info(f'Started container: {container.id}')

    def rm(self, name: str):
        try:
            container = self.docker_client.containers.get(name)
            container.stop()
            container.remove()
        except docker.errors.NotFound:
            pass

    def logs(self, name: str, stdout: bool = True, stderr: bool = True) \
            -> Iterator[str]:
        container = self.docker_client.containers.get(name)
        return container.logs(stdout=stdout, stderr=stderr,
                              stream=True, follow=True)

    @staticmethod
    def _is_container_id(container_id: str):
        if len(container_id) != 64:
            return False
        try:
            int(container_id, 16)
        except ValueError:
            return False
        return True
