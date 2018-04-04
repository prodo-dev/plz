import multiprocessing
import os
import shlex
import socket
import threading
import time
from contextlib import closing
from typing import Dict, Iterator, List, Optional

import boto3

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, InstanceProvider
from plz.controller.instances.instance_cache import InstanceCache
from plz.controller.volumes import Volumes
from .ec2_instance import EC2Instance, get_tag

DOCKER_PORT = 2375


class EC2InstanceGroup(InstanceProvider):
    MAX_IDLE_SECONDS = 60 * 30

    _INITIALIZATION_CODE_PATH = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'startup', 'startup.yml'))
    _CACHE_DEVICE = '/dev/xvdx'

    _name_to_group = {}
    _name_to_group_lock = threading.RLock()

    @staticmethod
    def from_config(config):
        images = Images.from_config(config)
        return EC2InstanceGroup(
            name=config.environment_name,
            client=boto3.client('ec2'),
            aws_worker_ami=config.aws_worker_ami,
            aws_key_name=config.aws_key_name,
            images=images,
            acquisition_delay_in_seconds=10,
            max_acquisition_tries=5)

    def __new__(cls,
                name: str,
                client,
                aws_worker_ami: str,
                aws_key_name: str,
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
                 aws_worker_ami: str,
                 aws_key_name: Optional[str],
                 images: Images,
                 acquisition_delay_in_seconds: int,
                 max_acquisition_tries: int):
        self.name = name
        self.client = client
        self.aws_worker_ami = aws_worker_ami
        self.aws_key_name = aws_key_name
        self.images = images
        self.acquisition_delay_in_seconds = acquisition_delay_in_seconds
        self.max_acquisition_tries = max_acquisition_tries
        self.instances = EC2InstanceCache(
            client=client,
            images=images,
            filters=[
                {'Name': f'tag:{EC2Instance.GROUP_NAME_TAG}',
                 'Values': [self.name]}
            ],
        )
        self.lock = multiprocessing.RLock()
        # Lazily initialized by ami_id
        self._ami_id = None
        # Lazily initialized by _instance_initialization_code
        self._instance_initialization_code = None

    @property
    def ami_id(self) -> str:
        if self._ami_id is not None:
            return self._ami_id
        response = self.client.describe_images(
            Filters=[
                {
                    'Name': 'name',
                    'Values': [self.aws_worker_ami],
                },
            ],
        )
        self._ami_id = response['Images'][0]['ImageId']
        return self._ami_id

    def instance_iterator(self) -> Iterator[Instance]:
        return iter(self.instances)

    @property
    def instance_initialization_code(self) -> str:
        if self._instance_initialization_code is not None:
            return self._instance_initialization_code
        with open(self._INITIALIZATION_CODE_PATH, 'r') as f:
            initialization_code = f.read()
        self._instance_initialization_code = '\n'.join([
            '#!/bin/sh',
            '',
            'set -e',
            'set -u',
            '',
            'export HOME=/root',
            '',
            'cat > /tmp/playbook.yml <<EOF',
            initialization_code,
            'EOF',
            '',
            ' '.join([shlex.quote(s) for s in [
                'ansible-playbook',
                '--inventory=localhost,',
                '--connection=local',
                f'--extra-vars=device={self._CACHE_DEVICE}',
                '/tmp/playbook.yml',
            ]])
        ])
        return self._instance_initialization_code

    def acquire_instance(
            self,
            execution_id: str,
            execution_spec: dict,
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
            yield 'querying availability'
            instance_type = execution_spec.get('instance_type')
            instances_not_assigned = self.instances.running(
                filters=[
                    (f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                    ('instance-type', instance_type),
                ])
            if len(instances_not_assigned) > 0:
                instance_data = instances_not_assigned[0]
            else:
                yield 'requesting new instance'
                instance_data = self._ask_aws_for_new_instance(instance_type)
            dns_name = _get_dns_name(instance_data)
            yield f'worker dns name is: {dns_name}'

            instance = self.instances.construct_instance(
                execution_id, instance_data)
            instance.set_tags([
                {'Key': EC2Instance.EXECUTION_ID_TAG,
                 'Value': execution_id},
                {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                 'Value': str(self.MAX_IDLE_SECONDS)},
            ])
            self.instances[execution_id] = instance

        while tries_remaining > 0:
            tries_remaining -= 1
            if instance.is_up():
                yield 'started'
                return
            else:
                yield 'pending'
                time.sleep(delay_in_seconds)

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        return self.instances[execution_id]

    def push(self, image_tag):
        self.images.push(image_tag)

    def release_instance(self, execution_id: str,
                         idle_since_timestamp: Optional[int] = None):
        if idle_since_timestamp is None:
            idle_since_timestamp = int(time.time())
        with self.lock:
            instance = self.instances[execution_id]
            if instance:
                instance.cleanup()
                instance.set_tags([
                    {'Key': EC2Instance.EXECUTION_ID_TAG,
                     'Value': ''},
                    {'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
                     'Value': str(idle_since_timestamp)},
                ])
            del self.instances[execution_id]

    def _ask_aws_for_new_instance(self, instance_type: str) -> dict:
        response = self.client.run_instances(
            **self._get_instance_spec(instance_type),
            MinCount=1, MaxCount=1)
        return response['Instances'][0]

    def _get_instance_spec(self, instance_type) -> dict:
        spec = _BASE_INSTANCE_SPEC.copy()
        spec['ImageId'] = self.ami_id
        if self.aws_key_name:
            spec['KeyName'] = self.aws_key_name
        spec['TagSpecifications'] = [{
            'ResourceType': 'instance',
            'Tags': [
                {
                    'Key': EC2Instance.GROUP_NAME_TAG,
                    'Value': self.name
                },
                {
                    'Key': EC2Instance.EXECUTION_ID_TAG,
                    'Value': ''
                },
                {
                    'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                    # Give it one minute as to be claimed before being
                    # terminated by staying idle for too long
                    'Value': '60'
                },
                {
                    'Key': 'Name',
                    # Name of the group and timestamp
                    'Value': f'Plz {self.name} Worker - '
                             f'{int(time.time() * 1000)}'
                },
            ]
        }]
        spec['UserData'] = self.instance_initialization_code
        spec['InstanceType'] = instance_type
        return spec


class EC2InstanceCache(InstanceCache):
    def __init__(self, client, images: Images, filters: List[Dict[str, str]]):
        super().__init__()
        self.client = client
        self.images = images
        self.filters = filters

    def find_instance(
            self,
            execution_id: str,
            instance_data: Optional[dict] = None) \
            -> Optional[EC2Instance]:
        if not instance_data:
            try:
                instance_data = self.running(filters=[
                    (f'tag:{EC2Instance.EXECUTION_ID_TAG}', execution_id),
                ])[0]
            except IndexError:
                return None
        return self.construct_instance(execution_id, instance_data)

    def construct_instance(self, execution_id: str, instance_data: dict) \
            -> EC2Instance:
        dns_name = _get_dns_name(instance_data)
        docker_url = f'tcp://{dns_name}:{DOCKER_PORT}'
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

    def instance_exists(self, execution_id: str) -> bool:
        instance_data = self.running(filters=[
            (f'tag:{EC2Instance.EXECUTION_ID_TAG}', execution_id),
        ])
        return len(instance_data) > 0

    def list_instances(self) -> Iterator[EC2Instance]:
        for instance_data in self.running():
            execution_id = get_tag(instance_data, EC2Instance.EXECUTION_ID_TAG)
            yield self.find_instance(execution_id, instance_data)

    def running(self, filters: [(str, str)] = None):
        encoded_filters = [{'Name': n, 'Values': [v]}
                           for (n, v)
                           in (filters or [])]
        instance_state_filter = [{'Name': 'instance-state-name',
                                  'Values': ['running']}]
        response = self.client.describe_instances(
            Filters=self.filters + encoded_filters + instance_state_filter)
        return [instance
                for reservation in response['Reservations']
                for instance in reservation['Instances']]


def _is_socket_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def _get_dns_name(instance_data: dict) -> str:
    return instance_data['PrivateDnsName']


_BASE_INSTANCE_SPEC = {
    # TODO(sergio): set subnet id

    'InstanceType': 't2.micro',
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
