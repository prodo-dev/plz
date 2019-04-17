import calendar
import collections
import logging
from typing import Dict, Iterator, List, Optional

import dateutil.parser
import docker
import docker.errors
import requests
from docker.models.containers import Container
from docker.types import Mount

from plz.controller.api.exceptions import WorkerUnreachableException

ContainerState = collections.namedtuple(
    'ContainerState',
    ['running',
     'status',
     'success',
     'exit_code',
     'finished_at'])

log = logging.getLogger(__name__)


class Containers:
    _CONTAINER_NAME_PREFIX = 'plz-execution-id.'

    @staticmethod
    def for_host(docker_url):
        docker_client = docker.DockerClient(base_url=docker_url)
        return Containers(docker_client)

    def __init__(self, docker_client: docker.DockerClient):
        self.docker_client = docker_client

    def run(self,
            execution_id: str,
            repository: str,
            tag: str,
            environment: Dict[str,
                              str],
            mounts: List[Mount],
            docker_run_args: Dict[str,
                                  str]):
        image = f'{repository}:{tag}'
        if execution_id == '':
            raise ValueError('Empty execution id!')
        container = self.docker_client.containers.run(
            image=image,
            name=self._CONTAINER_NAME_PREFIX + execution_id,
            environment=environment,
            mounts=mounts,
            detach=True,
            **docker_run_args)
        log.info(f'Started container: {container.id}')

    def logs(self,
             execution_id: str,
             since: Optional[int],
             stdout: bool = True,
             stderr: bool = True) \
            -> Iterator[bytes]:
        container = self.from_execution_id(execution_id)
        return container.logs(stdout=stdout,
                              stderr=stderr,
                              stream=True,
                              follow=True,
                              since=since)

    def stop(self, name: str):
        try:
            container = self.from_execution_id(name)
        except docker.errors.NotFound:
            return
        container.stop()

    def rm(self, execution_id: str):
        try:
            container = self.from_execution_id(execution_id)
        except docker.errors.NotFound:
            return
        container.stop()
        container.remove()

    def get_state(self, execution_id: str) -> ContainerState:
        container = self.from_execution_id(execution_id)
        if not container:
            raise ContainerMissingException
        container_state = container.attrs['State']
        success = container_state['ExitCode'] == 0
        finished_at = _docker_date_to_timestamp(container_state['FinishedAt'])
        return ContainerState(running=container_state['Running'],
                              status=container_state['Status'],
                              success=success,
                              exit_code=container_state['ExitCode'],
                              finished_at=finished_at)

    def get_files(self, execution_id: str, path: str) -> Iterator[bytes]:
        container = self.from_execution_id(execution_id)
        tar, _ = container.get_archive(path)
        yield from tar

    def execution_ids(self):
        return [
            container.name[len(self._CONTAINER_NAME_PREFIX):]
            for container in self.docker_client.containers.list(all=True)
            if container.name.startswith(self._CONTAINER_NAME_PREFIX)
        ]

    def from_execution_id(self, execution_id: str) -> Optional[Container]:
        try:
            return self.docker_client.containers.get(
                self._CONTAINER_NAME_PREFIX + execution_id)
        except docker.errors.NotFound:
            return None
        except requests.exceptions.ConnectionError:
            log.exception('Connecting to worker')
            raise WorkerUnreachableException(execution_id)

    def kill(self, execution_id: str):
        container = self.from_execution_id(execution_id)
        container.kill()

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
    return int(
        calendar.timegm(dateutil.parser.parse(docker_date).utctimetuple()))


class ContainerMissingException(Exception):
    pass
