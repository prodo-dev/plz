import io
import json
from typing import Iterator, List, Optional

from docker.types import Mount

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import \
    ExecutionInfo, Instance, \
    InstanceStatus, InstanceStatusFailure, InstanceStatusSuccess, Parameters
from plz.controller.results import ResultsStorage
from plz.controller.volumes import \
    VolumeDirectory, VolumeEmptyDirectory, VolumeFile, Volumes


class DockerInstance(Instance):
    def __init__(self,
                 results_storage: ResultsStorage,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 execution_id: str):
        self.results_storage = results_storage
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.execution_id = execution_id

    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.RawIOBase]):
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
                                          target=Volumes.VOLUME_MOUNT)])

    def status(self) -> InstanceStatus:
        with self.results_storage.get(self.execution_id) as results:
            if results:
                status = results.status()
                if status == 0:
                    return InstanceStatusSuccess()
                else:
                    return InstanceStatusFailure(status)
            else:
                return super().status()

    def logs(self, stdout: bool = True, stderr: bool = True) \
            -> Iterator[bytes]:
        with self.results_storage.get(self.execution_id) as results:
            if results:
                return results.logs()
            else:
                return self.containers.logs(self.execution_id,
                                            stdout=stdout,
                                            stderr=stderr)

    def output_files_tarball(self) -> Iterator[bytes]:
        with self.results_storage.get(self.execution_id) as results:
            if results:
                return results.output_tarball()
            else:
                return self.volumes.get_files(self.volume_name,
                                              Volumes.OUTPUT_DIRECTORY)

    def stop_execution(self):
        self.containers.stop(self.execution_id)

    def cleanup(self):
        self.execution_id = ''
        self.containers.rm(self.execution_id)
        self.volumes.remove(self.volume_name)

    def dispose(self):
        raise RuntimeError('Cannot dispose of a docker instance')

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

    def set_execution_id(self, execution_id: str):
        self.execution_id = execution_id

    def container_state(self) -> Optional[dict]:
        if self.execution_id == '':
            return None
        return self.containers.get_state(self.execution_id)
