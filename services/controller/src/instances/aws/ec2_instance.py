import socket
import time
from contextlib import closing
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

    def logs(self, stdout: bool = True, stderr: bool = True):
        return self.containers.logs(self.execution_id,
                                    stdout=stdout,
                                    stderr=stderr)

    def cleanup(self):
        self.containers.rm(self.execution_id)

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)


class EC2Instances:
    DOCKER_PORT = 2375

    # We find available instances by looking at those in which
    # the Execution-Id tag is empty. The autoscaling group has this tag
    # with an empty value, and it is propagated to new instances.
    EXECUTION_ID_TAG = 'Execution-Id'

    def __init__(self,
                 client,
                 images: Images,
                 filters: List[Dict[str, str]],
                 acquisition_delay_in_seconds: int,
                 max_acquisition_tries: int):
        self.client = client
        self.images = images
        self.filters = filters
        self.acquisition_delay_in_seconds = acquisition_delay_in_seconds
        self.max_acquisition_tries = max_acquisition_tries

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        # Keep trying until the host has a hostname and the Docker port is open
        for i in range(self.max_acquisition_tries):
            response = self.client.describe_instances(
                Filters=self.filters + [
                    {'Name': 'instance-state-name',
                     'Values': ['running']},
                    {'Name': f'tag:{self.EXECUTION_ID_TAG}',
                     'Values': [execution_id]},
                ])
            instances = [instance
                         for reservation in response['Reservations']
                         for instance in reservation['Instances']]
            if instances:
                instance_data = instances[0]
                host = instance_data.get('PrivateDnsName')
                print(host, self.DOCKER_PORT)
                if host and _is_socket_open(host, self.DOCKER_PORT):
                    break
            time.sleep(self.acquisition_delay_in_seconds)
        else:
            return None

        try:
            docker_url = f'tcp://{host}:{self.DOCKER_PORT}'
            images = self.images.for_host(docker_url)
            containers = Containers.for_host(docker_url)
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
                {'Key': self.EXECUTION_ID_TAG,
                 'Value': execution_id}
            ])
        return instance

    def release_for(self, execution_id: str):
        instance = self.instance_for(execution_id)
        if instance:
            instance.cleanup()
            instance.set_tags([
                {'Key': self.EXECUTION_ID_TAG,
                 'Value': ''}
            ])


def _is_socket_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def _ssh_prefix(ip_address):
    return [
        'ssh',
        '-o', 'LogLevel=ERROR',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        f'ubuntu@{ip_address}']
