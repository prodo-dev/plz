import calendar
import collections
import logging
from typing import Dict, Iterator, List, Optional

import dateutil.parser
import docker
import docker.errors
from docker.models.containers import Container
from docker.types import Mount

ContainerState = collections.namedtuple(
    'ContainerState',
    ['running', 'status', 'success', 'exit_code', 'finished_at'])


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
            repository: str,
            tag: str,
            command: List[str],
            environment: Dict[str, str],
            mounts: List[Mount]):
        image = f'{repository}:{tag}'
        container = self.docker_client.containers.run(
            image=image,
            command=command,
            name=name,
            environment=environment,
            mounts=mounts,
            detach=True,
        )
        self.log.info(f'Started container: {container.id}')

    def rm(self, name: str):
        container = self._get_container(name)
        if not container:
            return
        container.stop()
        container.remove()

    def logs(self, name: str, stdout: bool = True, stderr: bool = True) \
            -> Iterator[str]:
        container = self._get_container(name)
        if not container:
            return iter([])
        return container.logs(
            stdout=stdout, stderr=stderr, stream=True, follow=True)

    def get_state(self, name) -> Optional[ContainerState]:
        container = self._get_container(name)
        if not container:
            return None
        container_state = container.attrs['State']
        success = container_state['ExitCode'] == 0
        finished_at = _docker_date_to_timestamp(container_state['FinishedAt'])
        return ContainerState(
            running=container_state['Running'],
            status=container_state['Status'],
            success=success,
            exit_code=container_state['ExitCode'],
            finished_at=finished_at)

    def stop(self, name):
        container = self._get_container(name)
        if not container:
            return
        container.stop()

    def _get_container(self, name: str) -> Optional[Container]:
        try:
            return self.docker_client.containers.get(name)
        except docker.errors.NotFound:
            return None

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
