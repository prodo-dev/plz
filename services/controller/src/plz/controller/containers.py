import calendar
import logging
from collections import namedtuple
from typing import Dict, Iterator, List, Optional

import dateutil.parser
import docker
import docker.errors
from docker.models.containers import Container
from docker.types import Mount

from plz.controller.images import Images

ContainerState = namedtuple('ContainerState',
                            ['running', 'status', 'finished_at'])


class Containers:
    log = logging.getLogger('containers')

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Containers(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def run(self,
            name: str,
            tag: str,
            command: List[str],
            environment: Dict[str, str],
            mounts: List[Mount]):
        image = f'{Images.DOCKER_REPOSITORY}:{tag}'
        container = self.docker_client.containers.run(
            image=image,
            command=command,
            name=name,
            environment=environment,
            mounts=mounts,
            detach=True,
        )
        self.log.info(f'Started container: {container.id}')

    def exists(self, name: str) -> bool:
        try:
            self.docker_client.containers.get(name)
            return True
        except docker.errors.NotFound:
            return False

    def list(self) -> Container:
        return self.docker_client.containers.list()

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

    def get_state(self, name) -> Optional[ContainerState]:
        container = self.docker_client.containers.get(name)
        container_state = container.attrs['State']
        return ContainerState(running=container_state['Running'],
                              status=container_state['Status'],
                              finished_at=_docker_date_to_timestamp(
                                  container_state['FinishedAt']
                              ))

    @staticmethod
    def _is_container_id(container_id: str):
        if len(container_id) != 64:
            return False
        try:
            int(container_id, 16)
        except ValueError:
            return False
        return True


def _docker_date_to_timestamp(docker_date):
    return int(calendar.timegm(
        dateutil.parser.parse(docker_date).utctimetuple()))
