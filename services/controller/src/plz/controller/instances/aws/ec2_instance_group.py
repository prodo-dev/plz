import io
import logging
import socket
import time
from contextlib import closing
from typing import Any, Dict, Iterator, List, Optional

from redis import StrictRedis

from plz.controller.containers import Containers
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, \
    InstanceProvider, Parameters
from plz.controller.results.results_base import ResultsStorage
from plz.controller.volumes import Volumes
from .ec2_instance import EC2Instance, InstanceUnavailableException, \
    get_aws_instances, get_tag, describe_instances


log = logging.getLogger(__name__)


class EC2InstanceGroup(InstanceProvider):
    DOCKER_PORT = 2375

    def __init__(self,
                 name,
                 redis: StrictRedis,
                 client,
                 aws_worker_ami: str,
                 aws_key_name: Optional[str],
                 results_storage: ResultsStorage,
                 images: Images,
                 acquisition_delay_in_seconds: int,
                 max_acquisition_tries: int,
                 worker_security_group_names: [str],
                 use_public_dns: bool,
                 instance_lock_timeout: int):
        super().__init__(results_storage, instance_lock_timeout)
        self.name = name
        self.redis = redis
        self.client = client
        self.aws_worker_ami = aws_worker_ami
        self.aws_key_name = aws_key_name
        self.results_storage = results_storage
        self.images = images
        self.acquisition_delay_in_seconds = acquisition_delay_in_seconds
        self.max_acquisition_tries = max_acquisition_tries
        self.instances: Dict[str, EC2Instance] = {}
        self.worker_security_group_names = worker_security_group_names
        self.use_public_dns = use_public_dns
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

    def instance_iterator(self, only_running: bool) -> Iterator[Instance]:
        for instance_data in self._get_group_aws_instances([], only_running):
            yield self._ec2_instance_from_instance_data(instance_data)

    def get_forensics(self, execution_id) -> dict:
        instance = self.instance_for(execution_id)
        if instance is None:
            return {}
        return instance.get_forensics()

    def run_in_instance(
            self,
            execution_id: str,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            instance_market_spec: dict,
            execution_spec: dict,
            max_tries: int = 30,
            delay_in_seconds: int = 5) -> Iterator[Dict[str, Any]]:
        """
        Gets an available instance for the execution with the given id.

        If there's at least one instance in the group that is idle, assign the
        execution ID to it and return it. Otherwise, start a new box.
        """
        tries_remaining = max_tries
        yield _msg('querying availability')
        instance_type = execution_spec.get('instance_type')
        instance_max_uptime_in_minutes = execution_spec.get(
            'instance_max_uptime_in_minutes')
        instance_data = None
        instance: EC2Instance = None
        # Just to make the IDE happy, it's initialised in all execution paths
        is_instance_newly_created = False
        while tries_remaining > 0:
            tries_remaining -= 1
            if instance_data is None:
                instances_not_assigned = self._get_group_aws_instances(
                    only_running=True,
                    filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                             (f'tag:{EC2Instance.EARMARK_EXECUTION_ID_TAG}',
                              ''),
                             ('instance-type', instance_type)])
                if len(instances_not_assigned) > 0:
                    yield _msg('reusing existing instance')
                    is_instance_newly_created = False
                    instance_data = instances_not_assigned[0]
                else:
                    yield _msg('requesting new instance')
                    is_instance_newly_created = True
                    instance_data = self._ask_aws_for_new_instance(
                        instance_type,
                        instance_max_uptime_in_minutes,
                        instance_market_spec,
                        execution_id)
                yield _msg(
                    f'waiting for the instance to be ready')

            # When the dns name is public, it takes some time to show up. Make
            # sure there's a dns name before building the instance object
            if instance is None:
                # Get a fresh view of the instance data
                instance_data = describe_instances(
                    self.client,
                    filters=[('instance-id', instance_data['InstanceId'])])[0]
                dns_name = self._get_dns_name(instance_data)
                if dns_name != '':
                    instance = self._ec2_instance_from_instance_data(
                        instance_data, container_execution_id=execution_id)
                    try:
                        instance.earmark_for(execution_id)
                    except InstanceUnavailableException as e:
                        log.info(e)
                        yield _msg('taken while waiting')
                        instance_data = None
                        instance = None
                        continue
                    yield _msg(f'DNS name is: {dns_name}')

            if instance is not None and instance.is_up(
                    is_instance_newly_created):
                yield _msg('starting container')
                try:
                    instance.run(
                        command=command,
                        snapshot_id=snapshot_id,
                        parameters=parameters,
                        input_stream=input_stream,
                        docker_run_args=execution_spec['docker_run_args'],
                        max_idle_seconds=instance_market_spec[
                            'instance_max_idle_time_in_minutes']*60)
                except InstanceUnavailableException as e:
                    log.info(e)
                    yield _msg('gone while waiting')
                    # noinspection PyBroadException
                    try:
                        instance.unearmark_for(execution_id)
                    # Because the instance was earmarked (if things had gone
                    # the normal way), it it's unavailable then something
                    # undesirable happened (like, it's not running any more).
                    # Try to unearmark but catch any exceptions
                    except Exception:
                        log.exception('Exception unearmarking instance')
                    instance_data = self._ask_aws_for_new_instance(
                        instance_type,
                        instance_max_uptime_in_minutes,
                        instance_market_spec,
                        execution_id)
                    instance = None
                    continue
                yield _msg('running')
                yield {'instance': instance}
                return
            else:
                yield _msg('pending')
                time.sleep(delay_in_seconds)

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        instance_data_list = self._get_group_aws_instances(
            filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', execution_id)],
            only_running=False)
        if len(instance_data_list) == 0:
            return None
        elif len(instance_data_list) > 1:
            raise ValueError(
                f'More than one instance for execution ID {execution_id}')
        return self._ec2_instance_from_instance_data(instance_data_list[0])

    def release_instance(self, execution_id: str,
                         fail_if_not_found: bool = True,
                         idle_since_timestamp: Optional[int] = None):
        if idle_since_timestamp is None:
            idle_since_timestamp = int(time.time())
        super().release_instance(execution_id,
                                 fail_if_not_found,
                                 idle_since_timestamp)

    def push(self, image_tag):
        self.images.push(image_tag)

    def _get_group_aws_instances(self, filters, only_running: bool):
        filters += [(f'tag:{EC2Instance.GROUP_NAME_TAG}', self.name)]
        return get_aws_instances(
            self.client, filters, only_running=only_running)

    def _ask_aws_for_new_instance(
            self, instance_type: str,
            instance_max_uptime_in_minutes: Optional[int],
            instance_market_spec: dict,
            execution_id: str) -> dict:
        response = self.client.run_instances(
            **self._get_instance_spec(instance_type,
                                      instance_max_uptime_in_minutes,
                                      instance_market_spec, execution_id),
            MinCount=1, MaxCount=1)
        return response['Instances'][0]

    def _ec2_instance_from_instance_data(
            self, instance_data, container_execution_id=None) -> EC2Instance:
        if container_execution_id is None:
            container_execution_id = get_tag(
                instance_data, EC2Instance.EXECUTION_ID_TAG)
        dns_name = self._get_dns_name(instance_data)
        docker_url = f'tcp://{dns_name}:{self.DOCKER_PORT}'
        images = self.images.for_host(docker_url)
        containers = Containers.for_host(docker_url)
        volumes = Volumes.for_host(docker_url)
        return EC2Instance(
            self.client,
            images,
            containers,
            volumes,
            container_execution_id,
            instance_data,
            self.redis,
            self.instance_lock_timeout)

    def _get_instance_spec(self, instance_type: str,
                           instance_max_uptime_in_minutes: Optional[int],
                           instance_market_spec: dict,
                           execution_id: str) -> dict:
        spec = {'ImageId': self.ami_id}
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
                    'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
                    'Value': str(int(time.time()))
                },
                {
                    'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                    # Give it 20 minutes as to be claimed before being
                    # terminated by staying idle for too long
                    'Value': str(20 * 60)
                },
                {
                    'Key': EC2Instance.EARMARK_EXECUTION_ID_TAG,
                    'Value': execution_id
                },
                {
                    'Key': 'Name',
                    # Name of the group and timestamp
                    'Value': f'Plz {self.name} Worker - '
                             f'{int(time.time() * 1000)}'
                },
            ]
        }]
        shutdown_line = f'shutdown +{instance_max_uptime_in_minutes}' \
            if instance_max_uptime_in_minutes else ''
        # Script to execute at the beginning. We need to start the nvidia
        # persistence daemon. This is needed because otherwise containers might
        # take too long to start and docker might timeout when starting them
        spec['UserData'] = '\n'.join([
            '#!/bin/sh',
            shutdown_line,
            'nvidia-persistenced',
            ''])
        spec['InstanceType'] = instance_type
        if instance_market_spec['instance_market_type'] == 'spot':
            spec['InstanceMarketOptions'] = {
                'MarketType': instance_market_spec['instance_market_type'],
                'SpotOptions': {
                    'MaxPrice': str(
                        instance_market_spec[
                            'max_bid_price_in_dollars_per_hour']),
                }
            }
        if len(self.worker_security_group_names) != 0:
            spec['SecurityGroups'] = self.worker_security_group_names
        return spec

    def _get_dns_name(self, instance_data: dict) -> str:
        if self.use_public_dns:
            return instance_data['PublicDnsName']
        else:
            return instance_data['PrivateDnsName']


def _is_socket_open(host: str, port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex((host, port)) == 0


def _msg(s) -> Dict:
        return {'message': s}
