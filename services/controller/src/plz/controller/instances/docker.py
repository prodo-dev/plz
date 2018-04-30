import io
import json
import logging
from typing import Dict, Iterator, List, Optional

from docker.types import Mount
from redis import StrictRedis

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import \
    ExecutionInfo, Instance, Parameters
from plz.controller.results import ResultsStorage
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
            docker_run_args: Dict[str, str]):
        configuration = {
            'input_directory': Volumes.INPUT_DIRECTORY_PATH,
            'output_directory': Volumes.OUTPUT_DIRECTORY_PATH,
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
        return self.volumes.get_files(self.volume_name,
                                      Volumes.OUTPUT_DIRECTORY)

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

    def set_execution_id(self, execution_id: str, _: int, _lock_held=False):
        if _lock_held:
            self.execution_id = execution_id
        else:
            with self._lock:
                self.execution_id = execution_id
        return True

    def container_state(self) -> Optional[dict]:
        if self.execution_id == '':
            return None
        return self.containers.get_state(self.execution_id)

    def release(self,
                results_storage: ResultsStorage,
                _: int,
                release_container: bool = False,
                _lock_held: bool = False):
        if not release_container:
            # Everything to release here is about the container
            return
        # Passing a boolean is not the most elegant way to do it, but it's
        # easy to see that it works (regardless of whether there are several
        # instance objects with the same instance id, etc.). When it's about
        # concurrency, that's enough for me
        if _lock_held:
            self._do_release(results_storage)
        else:
            with self._lock:
                self._do_release(results_storage)

    def _do_release(self,
                    results_storage: ResultsStorage):

        self.stop_execution()
        self._publish_results(results_storage)
        # Check that we could collect the logs before destroying the container
        results_storage.check_logs_available(self.execution_id)
        self._cleanup()

    def _publish_results(self, results_storage: ResultsStorage):
        results_storage.publish(
            self.get_execution_id(),
            exit_status=self.exit_status(),
            logs=self.logs(since=None),
            output_tarball=self.output_files_tarball())

    @property
    def _instance_id(self):
        return self.execution_id
