import logging
from typing import Iterator, Optional

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base \
    import Instance, InstanceProvider
from plz.controller.volumes import Volumes

log = logging.getLogger(__name__)


class Localhost(InstanceProvider):
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

    def release_instance(self, execution_id: str,
                         idle_since_timestamp: Optional[int] = None):
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

    def instance_iterator(self) \
            -> Iterator[Instance]:
        return iter(self.instances.values())

    def stop_execution(self, execution_id):
        self.containers.stop(execution_id)
