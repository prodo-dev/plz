import logging
from typing import Dict, Iterator, Optional

from redis import StrictRedis

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base \
    import Instance, InstanceProvider
from plz.controller.results.results_base import ResultsStorage
from plz.controller.volumes import Volumes

log = logging.getLogger(__name__)


class Localhost(InstanceProvider):
    def __init__(self,
                 results_storage: ResultsStorage,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 redis: StrictRedis):
        super().__init__(results_storage)
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.results_storage = results_storage
        self.redis = redis

    def acquire_instance(
            self, execution_id: str, execution_spec: dict) -> Iterator[Dict]:
        """
        "Acquires" an instance.
        """
        instance = DockerInstance(
            self.images,
            self.containers,
            self.volumes,
            execution_id,
            self.redis)
        return iter([{'instance': instance}])

    def instance_for(self, execution_id: str) -> Optional[Instance]:
        """
        "Gets" the instance assigned to the execution ID.

        As we're dealing with `localhost` here, it's always the same instance,
        but the return value knows about the container under the hood.
        """
        if execution_id not in self.containers.execution_ids():
            log.error(f'Looking for:{execution_id}')
            log.error(f'Names are:{self.containers.execution_ids()}')
            return None
        return DockerInstance(
            self.images,
            self.containers,
            self.volumes,
            execution_id,
            self.redis)

    def stop_execution(self, execution_id):
        self.containers.stop(execution_id)

    def push(self, image_tag: str):
        pass

    def instance_iterator(self) \
            -> Iterator[Instance]:
        return iter(self.instance_for(execution_id)
                    for execution_id in self.containers.execution_ids())
