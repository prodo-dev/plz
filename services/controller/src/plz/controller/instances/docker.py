import io
import json
import logging
import os
from typing import Dict, Iterator, List, Optional

from docker.types import Mount
from redis import StrictRedis

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import \
    ExecutionInfo, Instance, Parameters
from plz.controller.results import ResultsStorage
from plz.controller.results.results_base import CouldNotGetOutputException
from plz.controller.volumes import \
    VolumeDirectory, VolumeEmptyDirectory, VolumeFile, Volumes

log = logging.getLogger(__name__)


class DockerInstance(Instance):
    def __init__(self,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 execution_id: str,
                 redis: StrictRedis):
        super().__init__(redis)
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.execution_id = execution_id

    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.RawIOBase],
            docker_run_args: Dict[str, str]) -> None:
        configuration = {
            'input_directory': Volumes.INPUT_DIRECTORY_PATH,
            'output_directory': Volumes.OUTPUT_DIRECTORY_PATH,
            'measures_directory': Volumes.MEASURES_DIRECTORY_PATH,
            'summary_measures_file_name': os.path.join(
                Volumes.MEASURES_DIRECTORY_PATH, 'summary'),
            'parameters': parameters
        }
        environment = {
            'CONFIGURATION_FILE': Volumes.CONFIGURATION_FILE_PATH
        }
        volume = self.volumes.create(self.volume_name, [
            VolumeDirectory(
                Volumes.INPUT_DIRECTORY,
                contents_tarball=input_stream or io.BytesIO()),
            VolumeEmptyDirectory(Volumes.OUTPUT_DIRECTORY),
            VolumeEmptyDirectory(Volumes.MEASURES_DIRECTORY),
            VolumeFile(Volumes.CONFIGURATION_FILE,
                       contents=json.dumps(configuration, indent=2)),
        ])
        self.containers.run(execution_id=self.execution_id,
                            repository=self.images.repository,
                            tag=snapshot_id,
                            command=command,
                            environment=environment,
                            mounts=[Mount(source=volume.name,
                                          target=Volumes.VOLUME_MOUNT)],
                            docker_run_args=docker_run_args)

    def logs(self, since: Optional[int], stdout: bool = True,
             stderr: bool = True) -> Iterator[bytes]:
        return self.containers.logs(self.execution_id,
                                    since,
                                    stdout=stdout,
                                    stderr=stderr)

    def output_files_tarball(self) -> Iterator[bytes]:
        return self.containers.get_files(
            self.execution_id, Volumes.OUTPUT_DIRECTORY_PATH)

    def measures_files_tarball(self) -> Iterator[bytes]:
        return self.containers.get_files(
            self.execution_id, Volumes.MEASURES_DIRECTORY_PATH)

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
            self, container_state: Optional[ContainerState] = None) -> int:
        # Doesn't make sense for local instances
        return 0

    def get_execution_id(self) -> str:
        return self.execution_id

    def get_instance_type(self) -> str:
        return 'local'

    def get_max_idle_seconds(self) -> int:
        # Doesn't make sense for local instances
        return 0

    def dispose_if_its_time(
            self, execution_info: Optional[ExecutionInfo] = None):
        # It's never time for a local instance
        pass

    def container_state(self) -> Optional[ContainerState]:
        if self.execution_id == '':
            return None
        return self.containers.get_state(self.execution_id)

    def release(self,
                results_storage: ResultsStorage,
                idle_since_timestamp: int,
                release_container: bool = True):
        if not release_container:
            # Everything to release here is about the container
            return
        with self._lock:
            self.stop_execution()
            self._publish_results(results_storage,
                                  finish_timestamp=idle_since_timestamp)
            # Check that we could collect the logs before destroying the
            # container
            if not results_storage.is_finished(self.execution_id):
                raise CouldNotGetOutputException(
                    f'Couldn\'t read the results for {self.execution_id}')
            self._cleanup()

    def _publish_results(self, results_storage: ResultsStorage,
                         finish_timestamp: int):
        results_storage.publish(
            self.get_execution_id(),
            exit_status=self.exit_status(),
            logs=self.logs(since=None),
            output_tarball=self.output_files_tarball(),
            measures_tarball=self.measures_files_tarball(),
            finish_timestamp=finish_timestamp)

    @property
    def _instance_id(self):
        return self.execution_id
