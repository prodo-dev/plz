import logging
import os.path
from typing import List

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base import Instance, Parameters
from plz.controller.volumes import Volumes

log = logging.getLogger('controller')


class EC2Instance(Instance):
    ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')

    def __init__(self,
                 client,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 execution_id: str,
                 data: dict):
        self.client = client
        self.images = images
        self.delegate = DockerInstance(
            images, containers, volumes, execution_id)
        self.data = data

    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters):
        self.images.pull(snapshot_id)
        self.delegate.run(command, snapshot_id, parameters)

    def logs(self, stdout: bool = True, stderr: bool = True):
        return self.delegate.logs(stdout, stderr)

    def is_up(self):
        return self.images.can_pull()

    def output_files_tarball(self):
        return self.delegate.output_files_tarball()

    def cleanup(self):
        return self.delegate.cleanup()

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)

    def get_container_status(self, execution_id) -> str:
        return self.delegate.get_container_status(execution_id)