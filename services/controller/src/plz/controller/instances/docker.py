import json
from typing import List, Optional

from docker.types import Mount

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import \
    ExecutionInfo, Instance, Parameters
from plz.controller.instances.instance_cache import InstanceCache
from plz.controller.volumes import VolumeDirectory, VolumeFile, Volumes


class DockerInstance(Instance):
    def __init__(self,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 execution_id: str):
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.execution_id = execution_id

    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters):
        configuration = {
            'output_directory': Volumes.OUTPUT_DIRECTORY_PATH,
            'parameters': parameters
        }
        volume = self.volumes.create(self.volume_name, [
            VolumeDirectory(Volumes.OUTPUT_DIRECTORY),
            VolumeFile(Volumes.CONFIGURATION_FILE,
                       contents=json.dumps(configuration, indent=2)),
        ])
        environment = {
            'CONFIGURATION_FILE': Volumes.CONFIGURATION_FILE_PATH
        }
        self.containers.run(name=self.execution_id,
                            tag=snapshot_id,
                            command=command,
                            environment=environment,
                            mounts=[Mount(source=volume.name,
                                          target=Volumes.VOLUME_MOUNT)])

    def stop_command(self):
        self.containers.stop(self.execution_id)

    def logs(self, stdout: bool = True, stderr: bool = True):
        return self.containers.logs(self.execution_id,
                                    stdout=stdout,
                                    stderr=stderr)

    def output_files_tarball(self):
        return self.volumes.get_files(self.volume_name,
                                      Volumes.OUTPUT_DIRECTORY)

    def cleanup(self):
        self.containers.rm(self.execution_id)
        self.volumes.remove(self.volume_name)

    def get_container_state(self) -> Optional[dict]:
        if self.execution_id == '':
            return None
        return self.containers.get_state(self.execution_id)

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


class DockerInstanceCache(InstanceCache):
    def __init__(self,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes):
        super().__init__()
        self.images = images
        self.containers = containers
        self.volumes = volumes

    def find_instance(self, execution_id: str) -> Optional[Instance]:
        return DockerInstance(
            self.images, self.containers, self.volumes, execution_id)

    def instance_exists(self, execution_id: str) -> bool:
        return self.containers.exists(execution_id)

    def list_instances(self) -> List[Instance]:
        return [self.find_instance(container.id)
                for container
                in self.containers.list()]
