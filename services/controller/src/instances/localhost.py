import logging
from typing import Iterator, Optional

from containers import Containers
from images import Images
from instances.docker import DockerInstance
from instances.instance_base import InstanceProvider, Instance
from volumes import Volumes

log = logging.getLogger('localhost')


class Localhost(InstanceProvider):
    @staticmethod
    def from_config(config):
        images = Images.from_config(config)
        containers = Containers.for_host(config.docker_host)
        volumes = Volumes.for_host(config.docker_host)
        return Localhost(images, containers, volumes)

    def __init__(self,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes):
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.instances = {}

    def acquire_instance(
            self, execution_id: str, execution_spec: dict) \
            -> Iterator[str]:
        """
        "Acquires" an instance.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        self.instances[execution_id] = DockerInstance(
            self.images, self.containers, self.volumes, execution_id)
        return iter([])

    def release_instance(self, execution_id: str):
        """
        "Releases" an instance.

        As we're dealing with `localhost` here, this doesn't do much.
        """
        self.instance_for(execution_id).cleanup()
        del self.instances[execution_id]

    def instance_for(self, execution_id: str) -> Optional[Instance]:
        """
        "Gets" the instance assigned to the execution ID.

        As we're dealing with `localhost` here, it's always the same instance.
        """
        return self.instances.get(execution_id)

    def push(self, image_tag: str):
        pass
