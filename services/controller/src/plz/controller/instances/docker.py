import json
from typing import List

from docker.types import Mount

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, Parameters
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

    @property
    def volume_name(self):
        return f'plz-{self.execution_id}'
