import os
import socket
import threading
import time
from contextlib import closing
from typing import Iterator, Tuple, Optional

import boto3

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import (
    InstanceProvider, ExecutionInfo, Instance)
from plz.controller.volumes import Volumes
from .ec2_instance import EC2Instance, get_tag


class EC2InstanceGroup(InstanceProvider):
    DOCKER_PORT = 2375

    # TODO(sergio): make this into a proper variable
    _AMI_TAG = "2018-03-01"

    _name_to_group = {}
    _name_to_group_lock = threading.RLock()

    @staticmethod
    def from_config(config):
        name = config.environment_name
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
                    'Values': [f'plz-worker-{self._AMI_TAG}']
                },
            ],
        )
        self._ami_id = response['Images'][0]['ImageId']
        return self._ami_id

    def execution_id_and_instance_iterator(self) -> Iterator[Tuple[str, Instance]]:
        for instance_data in self._get_running_aws_instances([]):
            execution_id = get_tag(instance_data, EC2Instance.EXECUTION_ID_TAG)
            yield execution_id, self._create_or_retrieve_instance_for(
                instance_data, execution_id)

    @property
    def instance_initialization_code(self) -> str:
        if self._instance_initialization_code is not None:
            return self._instance_initialization_code
        path_to_initialization_code = os.path.join(
            os.path.dirname(__file__),
            '..', '..', '..', '..', 'scripts',
            'initialize-cache')
        with open(path_to_initialization_code, 'r') as f:
            initialization_code = f.read()
        self._instance_initialization_code = \
            initialization_code.replace('$1', '/dev/xvdx')
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
            instances_not_assigned = self._get_running_aws_instances([
                (f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                ('instance-type', instance_type)])
            if len(instances_not_assigned) > 0:
                instance_data = instances_not_assigned[0]
            else:
                yield 'requesting new instance'
                instance_data = self._ask_aws_for_new_instance(instance_type)
            dns_name = _get_dns_name(instance_data)
            yield f'worker dns name is: {dns_name}'
            while tries_remaining > 0:
                tries_remaining -= 1
                instance = self._ec2_instance_from_instance_data(
                    instance_data, execution_id)
                if instance.is_up():

                    self._assign_aws_instance_to_execution_id(
                        instance, execution_id,
                        # TODO(sergio): hardcoded to 30 minutes now, should
                        # be coming in the request
                        max_idle_seconds=60*30)
                    yield 'started'
                    return
                else:
                    yield 'pending'
                    time.sleep(delay_in_seconds)

    def instance_for(self, execution_id):
        return self.instances[execution_id]

    def push(self, image_tag):
        self.images.push(image_tag)

    def release_instance(self, execution_id: str,
                         idle_since_timestamp: Optional[int]=None):
        with self.lock:
            instance = self.instances[execution_id]
            instance.cleanup()
            instance.set_tags([
                {'Key': EC2Instance.EXECUTION_ID_TAG,
                 'Value': ''},
                {'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
                 'Value': str(int(time.time()))}
            ])
            del self.instances[execution_id]

    def get_commands(self) -> [ExecutionInfo]:
        return [instance.get_execution_info()
                for _, instance in self.execution_id_and_instance_iterator()]

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

    def _assign_aws_instance_to_execution_id(
            self, instance, execution_id: str, max_idle_seconds: int) -> EC2Instance:
        instance.set_tags([
            {'Key': EC2Instance.EXECUTION_ID_TAG,
             'Value': execution_id},
            {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
             'Value': str(max_idle_seconds)}
        ])
        self.instances[execution_id] = instance
        return instance

    def _ec2_instance_from_instance_data(self, instance_data, execution_id) \
            -> EC2Instance:
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

    def _create_or_retrieve_instance_for(
            self, instance_data: dict, execution_id: str) -> EC2Instance:
        try:
            instance = self.instance_for(execution_id)
        except KeyError:
            # Be resilient in case the controller has been restarted
            instance = self._ec2_instance_from_instance_data(
                instance_data, execution_id)
            with self.lock:
                if execution_id is not None and execution_id != '':
                    self.instances[execution_id] = instance
        return instance

    def _get_instance_spec(self, instance_type) -> dict:
        spec = _BASE_INSTANCE_SPEC.copy()
        spec['ImageId'] = self.ami_id
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
                    # Give it one minute as to be claimed before being terminated
                    # by staying idle so long
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
