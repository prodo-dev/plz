import logging
from typing import Dict, Iterator, Optional

import mounts
from containers import Containers
from images import Images
from instances.instance_base import Instance, InstanceProvider

log = logging.getLogger('localhost')


class LocalhostInstance(Instance):
    def __init__(self,
                 images: Images,
                 containers: Containers,
                 execution_id: str):
        self.images = images
        self.containers = containers
        self.execution_id = execution_id
        self.files_to_clean_up = set()

    def run(self, command: str, snapshot_id: str, files: Dict[str, str]):
        volume_mounts = mounts.create_files_for_mounting(files)
        self.files_to_clean_up.update(volume_mounts.keys())
        self.containers.run(name=self.execution_id,
                            tag=snapshot_id,
                            command=command,
                            volume_mounts=volume_mounts)

    def logs(self, stdout: bool = True, stderr: bool = True):
        return self.containers.logs(self.execution_id,
                                    stdout=stdout,
                                    stderr=stderr)

    def cleanup(self):
        self.containers.rm(self.execution_id)
        mounts.delete_files(self.files_to_clean_up)
        self.files_to_clean_up = set()


class Localhost(InstanceProvider):
    @staticmethod
    def from_config(config):
        images = Images.from_config(config)
        containers = Containers.for_host(config.docker_host)
        return Localhost(images, containers)

    def __init__(self, images: Images, containers: Containers):
        self.images = images
        self.containers = containers
        self.instances = {}

    def acquire_instance(self, execution_id: str) -> Iterator[str]:
        """
        "Acquires" an instance.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        self.instances[execution_id] = LocalhostInstance(
            self.images, self.containers, execution_id)
        return iter([])

    def release_instance(self, execution_id: str):
        """
        "Releases" an instance.

        As we're dealing with `localhost` here, this doesn't do much.
        """
        self.instance_for(execution_id).cleanup()
        del self.instances[execution_id]

    def instance_for(self, execution_id: str) -> Optional[LocalhostInstance]:
        """
        "Gets" the instance assigned to the execution ID.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        return self.instances.get(execution_id)

    def push(self, image_tag: str):
        pass
