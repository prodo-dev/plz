import collections
import os
import sys

import boto3
import docker
import pyhocon
from redis import StrictRedis

from plz.controller.containers import Containers
from plz.controller.images import ECRImages, LocalImages
from plz.controller.instances.aws.ec2_instance_group import EC2InstanceGroup
from plz.controller.instances.localhost import Localhost
from plz.controller.redis_db_storage import RedisDBStorage
from plz.controller.results import LocalResultsStorage
from plz.controller.volumes import Volumes

AMI_TAG = '2018-11-08'
WORKER_AMI = f'plz-worker-{AMI_TAG}'

Dependencies = collections.namedtuple(
    'Dependencies',
    ['redis', 'instance_provider', 'images', 'results_storage', 'db_storage'])


def load() -> pyhocon.ConfigTree:
    if os.environ.get('CONFIGURATION'):
        return load_from_string(os.environ['CONFIGURATION'])

    try:
        start = sys.argv.index('--') + 1
    except ValueError:
        start = 1
    args = sys.argv[start:]
    if len(args) == 1:
        return load_from_file(args[0])

    print(f'Usage: controller CONFIGURATION-FILE')
    sys.exit(2)


def load_from_string(string) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_string(string)


def load_from_file(path) -> pyhocon.ConfigTree:
    return pyhocon.ConfigFactory.parse_file(path)


def dependencies_from_config(config) -> Dependencies:
    redis = StrictRedis(host=config.get('redis_host', 'localhost'))
    # DB storage can only be redis for now, but in case we want to drop redis
    # for something else, or allow other DBs to be specified in the info,
    # the dependence on redis is nicely encapsulated here
    db_storage = _db_storage_from(redis)
    images = _images_from(config)
    results_storage = _results_storage_from(config, redis, db_storage)
    instance_provider = _instance_provider_from(
        config, images, redis, results_storage)
    return Dependencies(
        redis, instance_provider, images, results_storage, db_storage)


def _instance_provider_from(
        config, images, redis, results_storage):
    docker_host = get_docker_host_from_config(config)
    instance_provider_type = config.get('instances.provider', 'localhost')
    if instance_provider_type == 'localhost':
        containers = Containers.for_host(docker_host)
        volumes = Volumes.for_host(docker_host)
        instance_provider = Localhost(
            results_storage, images, containers, volumes, redis,
            config['assumptions.instance_lock_timeout'])
    elif instance_provider_type == 'aws-ec2':
        instance_provider = EC2InstanceGroup(
            redis=redis,
            client=boto3.client(
                service_name='ec2',
                region_name=config['instances.region']),
            aws_worker_ami=WORKER_AMI,
            aws_key_name=config.get('instances.key_name', None),
            results_storage=results_storage,
            images=images,
            acquisition_delay_in_seconds=config.get_int(
                'instances.acquisition_delay', 10),
            max_acquisition_tries=config.get_int(
                'instances.max_acquisition_tries', 5),
            name=config['instances.group_name'],
            worker_security_group_names=config.get(
                'instances.worker_security_group_names', []),
            use_public_dns=config.get('instances.use_public_dns', False),
            instance_lock_timeout=config['assumptions.instance_lock_timeout'],
            instance_max_startup_time_in_minutes=config[
                'assumptions.instance_max_startup_time_in_minutes'])
    else:
        raise ValueError('Invalid instance provider.')
    return instance_provider


def _images_from(config):
    images_type = config.get('images.provider', 'local')

    def docker_api_client_creator():
        return docker_client_from_config(config)

    if images_type == 'local':
        repository = config.get('images.repository', 'plz/builds')
        images = LocalImages(docker_api_client_creator, repository)
    elif images_type == 'aws-ecr':
        def ecr_client_creator():
            return boto3.client(service_name='ecr',
                                region_name=config['images.region'])
        repository_without_registry = config['images.repository']
        images = ECRImages(
            docker_api_client_creator, ecr_client_creator,
            repository_without_registry,
            config['assumptions.ecr_login_validity_in_minutes'])
    else:
        raise ValueError('Invalid image provider.')
    return images


def get_docker_host_from_config(config):
    return config.get('images.docker_host', None)


def docker_client_from_config(config):
    docker_host = get_docker_host_from_config(config)
    docker_api_client_timeout = config.get(
        'assumptions.docker_api_client_timeout_in_minutes', None)
    if docker_api_client_timeout is not None:
        client_extra_args = {'timeout': docker_api_client_timeout * 60}
    else:
        client_extra_args = {}
    return docker.APIClient(base_url=docker_host, **client_extra_args)


def _results_storage_from(config, redis, db_storage):
    results_storage_type = config.get('results.provider', 'local')
    if results_storage_type == 'local':
        directory = config.get('results.directory')
        results_storage = LocalResultsStorage(redis, db_storage, directory)
    elif results_storage_type == 'aws-s3':  # TODO: Implement this
        raise NotImplementedError('The AWS S3 provider is not implemented.')
    else:
        raise ValueError('Invalid results storage provider.')
    return results_storage


def _db_storage_from(redis):
    return RedisDBStorage(redis)
