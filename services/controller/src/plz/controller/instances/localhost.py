import io
import logging
from typing import Any, Dict, Iterator, Optional

from redis import StrictRedis

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base \
    import Instance, InstanceProvider, Parameters
from plz.controller.results.results_base import ResultsStorage
from plz.controller.volumes import Volumes

log = logging.getLogger(__name__)


class Localhost(InstanceProvider):
    def __init__(self,
                 results_storage: ResultsStorage,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 redis: StrictRedis,
                 instance_lock_timeout: int):
        super().__init__(results_storage, instance_lock_timeout)
        self.images = images
        self.containers = containers
        self.volumes = volumes
        self.results_storage = results_storage
        self.redis = redis

    def run_in_instance(self,
                        execution_id: str,
                        snapshot_id: str,
                        parameters: Parameters,
                        input_stream: Optional[io.BytesIO],
                        instance_market_spec: dict,
                        execution_spec: dict) -> Iterator[Dict[str, Any]]:
        """
        Runs a job in an instance, that happens to be always the localhost
        """
        instance = DockerInstance(self.images,
                                  self.containers,
                                  self.volumes,
                                  execution_id,
                                  self.redis,
                                  self.instance_lock_timeout)
        instance.run(snapshot_id=snapshot_id,
                     parameters=parameters,
                     input_stream=input_stream,
                     docker_run_args=execution_spec['docker_run_args'],
                     index_range_to_run=execution_spec['index_range_to_run'])
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
        return DockerInstance(self.images,
                              self.containers,
                              self.volumes,
                              execution_id,
                              self.redis,
                              self.instance_lock_timeout)

    def push(self, image_tag: str):
        pass

    def instance_iterator(self, only_running: bool) \
            -> Iterator[Instance]:
        return iter(
            self.instance_for(execution_id)
            for execution_id in self.containers.execution_ids())

    def get_forensics(self, execution_id) -> dict:
        return {}
