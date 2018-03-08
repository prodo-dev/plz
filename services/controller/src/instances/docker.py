import json
from typing import List

from docker.types import Mount

from containers import Containers
from images import Images
from instances.instance_base import Instance
from volumes import Volumes, VolumeDirectory, VolumeFile


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

    def run(self, command: List[str], snapshot_id: str):
        configuration = {
            'output_directory': Volumes.OUTPUT_DIRECTORY_PATH,
        }
        volume = self.volumes.create(self.volume_name, [
            VolumeDirectory(Volumes.OUTPUT_DIRECTORY),
            VolumeFile(Volumes.CONFIGURATION_FILE,
                       contents=json.dumps(configuration, indent=2)),
        ])
        command_with_arguments = command + [Volumes.CONFIGURATION_FILE_PATH]
        self.containers.run(name=self.execution_id,
                            tag=snapshot_id,
                            command=command_with_arguments,
                            mounts=[Mount(source=volume.name,
                                          target=Volumes.VOLUME_MOUNT)])

    def logs(self, stdout: bool = True, stderr: bool = True):
        return self.containers.logs(self.execution_id,
                                    stdout=stdout,
                                    stderr=stderr)

    def output(self):
        return self.volumes.extract(self.volume_name, Volumes.OUTPUT_DIRECTORY)

    def cleanup(self):
        self.containers.rm(self.execution_id)
        self.volumes.remove(self.volume_name)

    @property
    def volume_name(self):
        return f'batman-{self.execution_id}'
