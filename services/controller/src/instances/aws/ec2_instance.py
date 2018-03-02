from typing import Dict, Optional, List

from containers import Containers
from images import Images
from instances.instance_base import Instance


class EC2Instance(Instance):
    def __init__(self,
                 client,
                 images: Images,
                 containers: Containers,
                 execution_id: str,
                 data: dict):
        self.client = client
        self.images = images
        self.containers = containers
        self.execution_id = execution_id
        self.data = data

    def run(self, command: str, snapshot_id: str):
        self.images.pull(snapshot_id)
        self.containers.run(self.execution_id, snapshot_id, command)

    def logs(self):
        return self.containers.logs(self.execution_id)

    def cleanup(self):
        self.containers.rm(self.execution_id)

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)


class EC2Instances:
    # We find available instances by looking at those in which
    # the Execution-Id tag is empty. The autoscaling group has this tag
    # with an empty value, and it is propagated to new instances.
    _EXECUTION_ID_TAG = 'Execution-Id'

    def __init__(self, client, images: Images, filters: List[Dict[str, str]]):
        self.client = client
        self.images = images
        self.filters = filters

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        response = self.client.describe_instances(
            Filters=self.filters + [
                {'Name': f'tag:{self._EXECUTION_ID_TAG}',
                 'Values': [execution_id]},
            ])
        try:
            instance_data = response['Reservations'][0]['Instances'][0]
            ip_address = instance_data["PrivateIpAddress"]
            docker_host = f'tcp://{ip_address}:2375'
            images = self.images.for_host(docker_host)
            containers = Containers.for_host(docker_host)
            return EC2Instance(
                self.client,
                images,
                containers,
                execution_id,
                instance_data)
        except (KeyError, IndexError):
            return None

    def acquire_for(self, execution_id: str) -> Optional[EC2Instance]:
        instance = self.instance_for('')
        if instance:
            instance.set_tags([
                {'Key': self._EXECUTION_ID_TAG,
                 'Value': execution_id}
            ])
        return instance

    def release_for(self, execution_id: str):
        instance = self.instance_for(execution_id)
        if instance:
            instance.cleanup()
            instance.set_tags([
                {'Key': self._EXECUTION_ID_TAG,
                 'Value': ''}
            ])


def _ssh_prefix(ip_address):
    return [
        'ssh',
        '-o', 'LogLevel=ERROR',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        f'ubuntu@{ip_address}']
