import os
import shlex
import socket
import threading
import time
from contextlib import closing
from typing import Dict, Iterator, Optional

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, InstanceProvider
from plz.controller.volumes import Volumes
from .ec2_instance import EC2Instance, get_tag


class EC2InstanceGroup(InstanceProvider):
    DOCKER_PORT = 2375

    _INITIALIZATION_CODE_PATH = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'startup', 'startup.yml'))
    _CACHE_DEVICE = '/dev/xvdx'

    _name_to_group = {}
    _name_to_group_lock = threading.RLock()

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
        self.instances: Dict[str, EC2Instance] = {}
        self.lock = threading.RLock()
        self.filters = [{'Name': f'tag:{EC2Instance.GROUP_NAME_TAG}',
                         'Values': [self.name]}]
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
        for instance_data in self._get_running_aws_instances([]):
            yield self._ec2_instance_from_instance_data(instance_data)

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

        If there's at least one instance in the group that is idle, assign the
        execution ID to it and return it. Otherwise, start a new box.
        """
        tries_remaining = max_tries
        yield 'querying availability'
        instance_type = execution_spec.get('instance_type')
        instances_not_assigned = self._get_running_aws_instances([
            (f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
            ('instance-type', instance_type)])
        if len(instances_not_assigned) > 0:
            instance_data = instances_not_assigned[0]
        else:
            yield 'requesting new instance'
            instance_data = self._ask_aws_for_new_instance(instance_type)
        instance = self._ec2_instance_from_instance_data(instance_data)
        dns_name = _get_dns_name(instance_data)
        yield f'worker dns name is: {dns_name}'
        while tries_remaining > 0:
            tries_remaining -= 1
            if instance.is_up():
                with self.lock:
                    # Checking if it's still free
                    if self._is_instance_free(instance_data['InstanceId']):
                        instance.set_tags([
                            {'Key': EC2Instance.EXECUTION_ID_TAG,
                             'Value': execution_id},
                            # TODO(sergio): hardcoded to 30 minutes now,
                            # should be coming in the request
                            {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                             'Value': str(60 * 30)}
                        ])
                        yield 'started'
                        return
                yield 'taken while waiting'
                instance_data = self._ask_aws_for_new_instance(instance_type)
                instance = self._ec2_instance_from_instance_data(instance_data)
            else:
                yield 'pending'
                time.sleep(delay_in_seconds)

    def _is_instance_free(self, instance_id):
        instances = self._get_running_aws_instances(
            filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                     ('instance-id', instance_id)])
        return len(instances) > 0

    def instance_for(self, execution_id: str) -> EC2Instance:
        instance_data = self._get_running_aws_instances(
            filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', execution_id)])[0]
        return self._ec2_instance_from_instance_data(instance_data)

    def push(self, image_tag):
        self.images.push(image_tag)

    def release_instance(self, execution_id: str,
                         idle_since_timestamp: Optional[int] = None):
        if idle_since_timestamp is None:
            idle_since_timestamp = int(time.time())
        with self.lock:
            instance = self.instance_for(execution_id)
            instance.cleanup()
            instance.set_tags([
                {'Key': EC2Instance.EXECUTION_ID_TAG,
                 'Value': ''},
                {'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
                 'Value': str(idle_since_timestamp)}
            ])

    def stop_execution(self, execution_id: str):
        self.instance_for(execution_id).stop_execution()

    def _get_running_aws_instances(self, filters: [(str, str)]):
        new_filters = [{'Name': n, 'Values': [v]} for (n, v) in filters]
        instance_state_filter = [{'Name': 'instance-state-name',
                                  'Values': ['running']}]
        response = self.client.describe_instances(
            Filters=self.filters + new_filters + instance_state_filter)
        return [instance
                for reservation in response['Reservations']
                for instance in reservation['Instances']]

    def _ask_aws_for_new_instance(self, instance_type: str) -> dict:
        response = self.client.run_instances(
            **self._get_instance_spec(instance_type),
            MinCount=1, MaxCount=1)
        return response['Instances'][0]

    def _ec2_instance_from_instance_data(self, instance_data) \
            -> EC2Instance:
        execution_id = get_tag(instance_data, EC2Instance.EXECUTION_ID_TAG)
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
