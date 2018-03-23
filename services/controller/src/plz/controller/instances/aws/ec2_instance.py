import logging
import os.path
from typing import List, Optional

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base import (
    Instance, Parameters, ExecutionInfo)
from plz.controller.volumes import Volumes

log = logging.getLogger('controller')


class EC2Instance(Instance):
    ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')

    # We find available instances by looking at those in which
    # the Execution-Id tag is the empty string. Instances are
    # started with an empty value for this tag, the tag is set
    # when the instance starts executing, and it's emptied again
    # when the execution finishes
    EXECUTION_ID_TAG = 'Plz:Execution-Id'
    GROUP_NAME_TAG = 'Plz:Group-Id'
    MAX_IDLE_SECONDS_TAG = 'Plz:Max-Idle-Seconds'
    IDLE_SINCE_TIMESTAMP_TAG = 'Plz:Idle-Since-Timestamp'

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

    def dispose(self):
        self.client.terminate_instances(InstanceIds=[self.data['InstanceId']])

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)
        response = self.client.describe_instances(
            Filters=[{'Name': 'instance-id',
                      'Values': [instance_id]}])
        self.data = [instance
                     for reservation in response['Reservations']
                     for instance in reservation['Instances']][0]

    def get_container_state(self) -> Optional[dict]:
        return self.delegate.get_container_state()

    def get_execution_info(self) -> ExecutionInfo:
        execution_id = get_tag(
            self.data, self.EXECUTION_ID_TAG, '')
        max_idle_seconds = int(get_tag(
            self.data, self.MAX_IDLE_SECONDS_TAG, '0'))
        idle_since_timestamp = int(get_tag(
            self.data, self.IDLE_SINCE_TIMESTAMP_TAG, '0'))

        container_state = self.get_container_state()
        if container_state is not None:
            idle_since_timestamp = container_state['FinishedAt']
        return ExecutionInfo(
            instance_type=self.data['InstanceType'],
            execution_id=execution_id,
            container_state=container_state,
            idle_since_timestamp=idle_since_timestamp,
            max_idle_seconds=max_idle_seconds)


def get_tag(instance_data, tag, default=None) -> Optional[str]:
    for t in instance_data['Tags']:
        if t['Key'] == tag:
            return t['Value']
    return default
