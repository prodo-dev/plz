import logging

import boto3
import os.path
import socket
import threading
import time
from contextlib import closing
from typing import Dict, List, Optional, Iterator

from containers import Containers
from images import Images
from instances.docker import DockerInstance
from instances.instance_base import Instance, Parameters
from volumes import Volumes

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

    def output_files_tarball(self):
        return self.delegate.output_files_tarball()

    def cleanup(self):
        return self.delegate.cleanup()

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)


class EC2InstanceGroup:
    DOCKER_PORT = 2375

    # We find available instances by looking at those in which
    # the Execution-Id tag is empty. The autoscaling group has this tag
    # with an empty value, and it is propagated to new instances.
    EXECUTION_ID_TAG = 'Batman:Execution-Id'
    GROUP_NAME_TAG = 'Batman:Group-Id'

    # TODO(samir): (or Sergio with help) make this into a proper variable
    _AMI_TAG = "2018-03-01"

    _name_to_group = {}
    _name_to_group_lock = threading.RLock()

    @staticmethod
    def from_config(config):
        name = config.aws_autoscaling_group
        images = Images.from_config(config)
        return EC2InstanceGroup(
            name=name,
            client=boto3.client('ec2'),
            images=images,
            acquisition_delay_in_seconds=10,
            max_acquisition_tries=5)

    def __new__(cls,
                name: str,
                client,
                images: Images,
                acquisition_delay_in_seconds: int,
                max_acquisition_tries: int):
        with EC2InstanceGroup._name_to_group_lock:
            try:
                return EC2InstanceGroup._name_to_group[name]
            except KeyError:
                pass
            group = super().__new__(cls)
            EC2InstanceGroup._name_to_group[name] = group
            return group

    def __init__(self,
                 name,
                 client,
                 images: Images,
                 acquisition_delay_in_seconds: int,
                 max_acquisition_tries: int):
        self.name = name
        self.client = client
        self.images = images
        self.acquisition_delay_in_seconds = acquisition_delay_in_seconds
        self.max_acquisition_tries = max_acquisition_tries
        self.instances = {}
        self.lock = threading.RLock()
        self.filters = [{'Name': f'tag:{self.GROUP_NAME_TAG}',
                         'Values': [self.name]}]
        # Lazily initialized by get_ami_id
        self._ami_id = None

    def get_ami_id(self):
        if self._ami_id is not None:
            return self._ami_id
        response = self.client.describe_images(
            Filters=[
                {
                    'Name': 'name',
                    'Values': [
                        'batman-worker-' + self._AMI_TAG,
                    ]
                },
            ],
        )
        self._ami_id = response['Images'][0]['ImageId']
        return self._ami_id

    def acquire_instance(
            self,
            execution_id: str,
            max_tries: int = 30,
            delay_in_seconds: int = 10) \
            -> Iterator[str]:
        """
        Gets an available instance for the execution with the given id.

        If there's at least one instance in the group that is not running
        a command, assign the execution id to one of them and return it.
        Otherwise, increase the desired capacity of the group and try until
        the maximum number of trials.
        """
        tries_remaining = max_tries
        with self.lock:
            log = logging.getLogger('controller')
            yield 'querying availability'
            instances_not_assigned = self._aws_instances_by_execution_id('')
            if len(instances_not_assigned) > 0:
                instance_data = instances_not_assigned[0]
            else:
                yield 'requesting new instance'
                log.warning('Asking for new instance!')
                instance_data = self._ask_aws_for_new_instance()
                log.warning('Got new instance!')
            dns_name = _get_dns_name(instance_data)
            while tries_remaining > 0:
                tries_remaining -= 1
                log.warning('Trying!')
                if _is_socket_open(dns_name, self.DOCKER_PORT):
                    self._assign_aws_instance_to_execution_id(instance_data, execution_id)
                    yield 'started'
                    return
                else:
                    yield 'pending'
                    time.sleep(delay_in_seconds)

    def instance_for(self, execution_id):
        return self.instances[execution_id]

    def _aws_instances_by_execution_id(self, execution_id):
        response = self.client.describe_instances(
            Filters=self.filters + [
                {'Name': 'instance-state-name',
                 'Values': ['running']},
                {'Name': f'tag:{self.EXECUTION_ID_TAG}',
                 'Values': [execution_id]}
            ])
        return [instance
                for reservation in response['Reservations']
                for instance in reservation['Instances']]

    def _ask_aws_for_new_instance(self) -> dict:
        response = self.client.run_instances(
            **self._get_instance_spec(),
            MinCount=1, MaxCount=1)
        return response['Instances'][0]

    def _assign_aws_instance_to_execution_id(
            self, instance_data, execution_id: str) -> EC2Instance:
        instance = self._ec2_instance_from_instance_data(instance_data, execution_id)
        instance.set_tags([
            {'Key': self.EXECUTION_ID_TAG,
             'Value': execution_id}
        ])
        self.instances[execution_id] = instance
        return instance

    def _ec2_instance_from_instance_data(self, instance_data, execution_id):
        dns_name = _get_dns_name(instance_data)
        docker_url = f'tcp://{dns_name}:{self.DOCKER_PORT}'
        images = self.images.for_host(docker_url)
        containers = Containers.for_host(docker_url)
        volumes = Volumes.for_host(docker_url)
        return EC2Instance(
            self.client,
            images,
            containers,
            volumes,
            execution_id,
            instance_data)

    def release_for(self, execution_id: str):
        instance = self.instances[execution_id]
        instance.cleanup()
        instance.set_tags([
            {'Key': self.EXECUTION_ID_TAG,
             'Value': ''}
        ])
        del self.instances[execution_id]

    def _get_instance_spec(self) -> dict:
        spec = _BASE_INSTANCE_SPEC.copy()
        spec['ImageId'] = self.get_ami_id()
        spec['TagSpecifications'] = [{
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': EC2InstanceGroup.GROUP_NAME_TAG,
                    'Value': self.name
                },
                {
                    'Key': EC2InstanceGroup.EXECUTION_ID_TAG,
                    'Value': ''
                },
                {
                    'Key': 'Name',
                    'Value': 'Batman worker - ' + self.name
                },
            ]
        }]
        return spec


def _is_socket_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def _ssh_prefix(ip_address: str):
    return [
        'ssh',
        '-o', 'LogLevel=ERROR',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'UserKnownHostsFile=/dev/null',
        f'ubuntu@{ip_address}']


def _get_dns_name(instance_data: dict) -> str:
    return instance_data['PrivateDnsName']


_BASE_INSTANCE_SPEC = {
    # TODO(sergio): check with Samir. Should we care about the subnet id?
    # It's getting the same as the workers. Will it always be the case?

    'InstanceType': 't1.micro',
    'InstanceMarketOptions': {
        'MarketType': 'spot',
        'SpotOptions': {
            'MaxPrice': '1.0',
        }
    },
    'BlockDeviceMappings': [
        {
            'DeviceName': '/dev/sdx',
            'Ebs': {
                'VolumeSize': 100,
            },
        },
    ]
}
