import io
import json
import logging
from typing import Dict, Iterator, Optional, Tuple

import docker.errors
import time
from docker.types import Mount
from redis import StrictRedis

from plz.controller.api.exceptions import InstanceStillRunningException
from plz.controller.containers import ContainerState, Containers
from plz.controller.execution_composition import InstanceComposition
from plz.controller.images import Images
from plz.controller.instances.instance_base import ExecutionInfo, Instance, \
    KillingInstanceException, Parameters
from plz.controller.results import ResultsStorage
from plz.controller.results.results_base import CouldNotGetOutputException
from plz.controller.volumes import \
    VolumeDirectory, VolumeFile, Volumes

log = logging.getLogger(__name__)


class DockerInstance(Instance):
    def __init__(
            self,
            images: Images,
            containers: Containers,
            volumes: Volumes,
            execution_id: str,
            redis: StrictRedis,
            lock_timeout: int):
        super().__init__(redis, lock_timeout)
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.execution_id = execution_id

    def run(
            self,
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.RawIOBase],
            docker_run_args: Dict[str,
                                  str],
            index_range_to_run: Optional[Tuple[int,
                                               int]]) -> None:
        startup_config = InstanceComposition.create_for(
            index_range_to_run).get_startup_config()

        configuration = {
            'input_directory': Volumes.INPUT_DIRECTORY_PATH,
            **startup_config.config_keys,
            'parameters': parameters,
        }
        environment = {'CONFIGURATION_FILE': Volumes.CONFIGURATION_FILE_PATH}
        volume = self.volumes.create(
            self.volume_name,
            [
                VolumeDirectory(
                    Volumes.INPUT_DIRECTORY,
                    contents_tarball=input_stream or io.BytesIO()),
                *startup_config.volumes,
                VolumeFile(
                    Volumes.CONFIGURATION_FILE,
                    contents=json.dumps(configuration,
                                        indent=2)),
            ])
        self.containers.run(
            execution_id=self.execution_id,
            repository=self.images.repository,
            tag=snapshot_id,
            environment=environment,
            mounts=[Mount(source=volume.name,
                          target=Volumes.VOLUME_MOUNT)],
            docker_run_args=docker_run_args)

    def stop_execution(self):
        self.containers.stop(self.execution_id)

    def _cleanup(self):
        self.containers.rm(self.execution_id)
        self.volumes.remove(self.volume_name)
        self.execution_id = ''

    @property
    def volume_name(self):
        return f'plz-{self.execution_id}'

    def get_idle_since_timestamp(
            self,
            container_state: Optional[ContainerState] = None) -> int:
        # Doesn't make sense for local instances
        return 0

    def get_resource_state(self) -> str:
        # Docker is always running
        return 'running'

    def delete_resource(self) -> None:
        # No underlying resource to delete
        pass

    def get_execution_id(self) -> str:
        return self.execution_id

    def get_instance_type(self) -> str:
        return 'local'

    def get_max_idle_seconds(self) -> int:
        # Doesn't make sense for local instances
        return 0

    def dispose_if_its_time(
            self,
            execution_info: Optional[ExecutionInfo] = None):
        # It's never time for a local instance
        pass

    def kill(self, force_if_not_idle: bool):
        if not force_if_not_idle:
            raise KillingInstanceException(
                'Attempt to kill a running local container, which is not idle')
        try:
            # If the container has exited, when killing we only need to remove
            if self.containers.get_state(self.execution_id).status != 'exited':
                self.containers.kill(self.get_execution_id())
                for _ in range(0, 3, -1):
                    could_remove = False
                    try:
                        self.volumes.remove(self.volume_name)
                        could_remove = True
                    except docker.errors.APIError:
                        time.sleep(1)
                        pass
                    if not could_remove:
                        log.error(
                            f'Couldn\'t remove volume: {self.volume_name}')
            self.containers.rm(self.get_execution_id())
        except Exception as e:
            log.exception(e)
            raise KillingInstanceException(str(e)) from e

    def container_state(self) -> Optional[ContainerState]:
        if self.execution_id == '':
            return None
        return self.containers.get_state(self.execution_id)

    def release(
            self,
            results_storage: ResultsStorage,
            idle_since_timestamp: int,
            release_container: bool = True):
        log.debug(f'Releasing container of {self.execution_id}')
        if not release_container:
            # Everything to release here is about the container
            return
        with self._lock:
            log.debug(
                f'Stopping execution while releasing '
                f'{self.execution_id}')
            self.stop_execution()
            self._publish_results(
                results_storage,
                finish_timestamp=idle_since_timestamp)
            # Check that we could collect the logs before destroying the
            # container
            if not results_storage.is_finished(self.execution_id):
                raise CouldNotGetOutputException(
                    f'Couldn\'t read the results for {self.execution_id}')
            self._cleanup()

    def get_forensics(self) -> dict:
        return {}

    def _publish_results(
            self,
            results_storage: ResultsStorage,
            finish_timestamp: int):
        log.debug(f'Publishing results of {self.execution_id}')

        results_storage.publish(
            self.get_execution_id(),
            exit_status=self.get_status().exit_status,
            logs=self.get_logs(since=None),
            containers=self.containers,
            finish_timestamp=finish_timestamp)

    @property
    def instance_id(self):
        return 'docker:' + self.execution_id

    def get_logs(
            self,
            since: Optional[int] = None,
            stdout: bool = True,
            stderr: bool = True) -> Iterator[bytes]:
        return self.containers.logs(
            self.execution_id,
            since,
            stdout=stdout,
            stderr=stderr)

    def get_output_files_tarball(
            self, path: Optional[str], index: Optional[int]) \
            -> Iterator[bytes]:
        return InstanceComposition.get_output_tarball(
            self.containers,
            self.execution_id,
            index,
            path)

    def get_measures_files_tarball(self, index: Optional[int]) \
            -> Iterator[bytes]:
        return InstanceComposition.get_measures_tarball(
            self.containers,
            self.execution_id,
            index)

    def get_stored_metadata(self) -> dict:
        raise InstanceStillRunningException(self.execution_id)
