import os
import sys

import boto3
import docker
import pyhocon

from plz.controller.containers import Containers
from plz.controller.images import ECRImages
from plz.controller.images.local import LocalImages
from plz.controller.instances.aws import EC2InstanceGroup
from plz.controller.instances.instance_base import InstanceProvider
from plz.controller.instances.localhost import Localhost
from plz.controller.volumes import Volumes


def load() -> pyhocon.ConfigTree:
    if os.environ.get('CONFIGURATION'):
        return load_from_string(os.environ['CONFIGURATION'])
    if len(sys.argv) != 1:
        return load_from_file(sys.argv[1])
    else:
        print(f'Usage: {sys.argv[0]} CONFIGURATION-FILE')
        sys.exit(2)


def load_from_string(string) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_string(string)


def load_from_file(path) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_file(path)


def instance_provider_from_config(config) -> InstanceProvider:
    provider = config.get('instances.provider', 'localhost')
    docker_host = config.get('images.docker_host', None)
    images = images_from_config(config)
    if provider == 'localhost':
        containers = Containers.for_host(docker_host)
        volumes = Volumes.for_host(docker_host)
        return Localhost(images, containers, volumes)
    elif provider == 'aws-ec2':
        return EC2InstanceGroup(
            name=config['instances.group_name'],
            client=boto3.client(
                service_name='ec2',
                region_name=config['instances.region']),
            aws_worker_ami=config['instances.worker_ami'],
            aws_key_name=config['instances.key_name'],
            images=images,
            acquisition_delay_in_seconds=config.get_int(
                'instances.acquistion_delay', 10),
            max_acquisition_tries=config.get_int(
                'instances.max_acquisition_tries', 5))
    else:
        raise ValueError('Invalid instance provider.')


def images_from_config(config):
    provider = config.get('images.provider', 'local')
    docker_api_client = docker.APIClient(
        base_url=config.get('images.docker_host', None))
    if provider == 'local':
        repository = config.get('images.repository', 'plz/builds')
        return LocalImages(docker_api_client, repository)
    elif provider == 'aws-ecr':
        ecr_client = boto3.client(
            service_name='ecr',
            region_name=config['images.region'])
        repository = config['images.repository']
        return ECRImages(docker_api_client, ecr_client, repository)
    else:
        raise ValueError('Invalid image provider.')
