import calendar
import logging
from typing import Dict, Iterator, List, Optional

import dateutil.parser
import docker
import docker.errors
from docker.types import Mount

from plz.controller.images import Images


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

    def get_state(self, name) -> Optional[dict]:
        container = self.docker_client.containers.get(name)
        state = {a: container.attrs['State'][a]
                 for a in ['Status', 'Running']}
        finished_at = container.attrs['State'].get('FinishedAt')
        if finished_at is not None:
            # Convert from the string provided by docker to a
            # unix timestamp
            finished_at = int(calendar.timegm(
                dateutil.parser.parse(finished_at).utctimetuple()))
        state['FinishedAt'] = finished_at
        return state

    @staticmethod
    def _is_container_id(container_id: str):
        if len(container_id) != 64:
            return False
        try:
            int(container_id, 16)
        except ValueError:
            return False
        return True
