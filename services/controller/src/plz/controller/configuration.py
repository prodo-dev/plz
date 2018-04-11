import os
import sys

import boto3
import docker
import pyhocon
from redis import StrictRedis

from plz.controller.containers import Containers
from plz.controller.images import ECRImages, Images, LocalImages
from plz.controller.instances.aws import EC2InstanceGroups
from plz.controller.instances.instance_base import InstanceProvider
from plz.controller.instances.localhost import Localhost
from plz.controller.results import LocalResultsStorage, ResultsStorage
from plz.controller.volumes import Volumes

AMI_TAG = '2018-04-11'
WORKER_AMI = f'plz-worker-{AMI_TAG}'


def load() -> pyhocon.ConfigTree:
    if os.environ.get('CONFIGURATION'):
        return load_from_string(os.environ['CONFIGURATION'])

    try:
        start = sys.argv.index('--') + 1
    except ValueError:
        start = 0
    args = sys.argv[start:]
    if len(args) == 1:
        return load_from_file(args[0])

    print(f'Usage: controller CONFIGURATION-FILE')
    sys.exit(2)


def load_from_string(string) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_string(string)


def load_from_file(path) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_file(path)


def instance_provider_from_config(config) -> InstanceProvider:
    provider = config.get('instances.provider', 'localhost')
    docker_host = config.get('images.docker_host', None)
    images = images_from_config(config)
    results_storage = results_storage_from_config(config)
    if provider == 'localhost':
        containers = Containers.for_host(docker_host)
        volumes = Volumes.for_host(docker_host)
        return Localhost(images, containers, volumes, results_storage)
    elif provider == 'aws-ec2':
        groups = EC2InstanceGroups(
            redis=redis_from_config(config),
            client=boto3.client(
                service_name='ec2',
                region_name=config['instances.region']),
            aws_worker_ami=WORKER_AMI,
            aws_key_name=config['instances.key_name'],
            images=images,
            results_storage=results_storage,
            acquisition_delay_in_seconds=config.get_int(
                'instances.acquisition_delay', 10),
            max_acquisition_tries=config.get_int(
                'instances.max_acquisition_tries', 5))
        return groups.get(config['instances.group_name'])
    else:
        raise ValueError('Invalid instance provider.')


def images_from_config(config) -> Images:
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


def results_storage_from_config(config) -> ResultsStorage:
    provider = config.get('results.provider', 'local')
    if provider == 'local':
        redis = redis_from_config(config)
        directory = config.get('results.directory')
        return LocalResultsStorage(redis, directory)
    elif provider == 'aws-s3':  # TODO: Implement this
        raise NotImplementedError('The AWS S3 provider is not implemented.')
    else:
        raise ValueError('Invalid results storage provider.')


def redis_from_config(config) -> StrictRedis:
    return StrictRedis(
        host=config.get('redis_host', 'localhost'))
