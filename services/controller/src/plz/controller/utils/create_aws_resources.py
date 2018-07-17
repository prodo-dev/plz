import json
import logging
from logging import INFO

import boto3
import sys

from docker import APIClient

from plz.controller import configuration
from plz.controller.configuration import dependencies_from_config, \
    Dependencies, docker_client_from_config
from plz.controller.images import ECRImages

config = configuration.load()


def create_workers_security_group():
    ec2_client = boto3.client(
        service_name='ec2',
        region_name=config['instances.region'])
    group_exists = len(
        ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name',
                      'Values': ['plz-workers']}])['SecurityGroups']) > 0
    if group_exists:
        print('Security group for workers already exists', file=sys.stderr,
              flush=True)
        return

    print('Creating security group for workers', file=sys.stderr, flush=True)

    response = ec2_client.create_security_group(
        Description='Plz group for workers',
        GroupName='plz-workers')
    group_id = response['GroupId']

    # Authorize the docker port
    ec2_client.authorize_security_group_ingress(
        GroupId=group_id,
        IpPermissions=[
            {
                'IpRanges': [
                    {
                        'CidrIp': '0.0.0.0/0'
                    },
                ],
                'Ipv6Ranges': [
                    {
                        'CidrIpv6': '::/0'
                    }
                ],
                'FromPort': 2375,
                'ToPort': 2375,
                'IpProtocol': 'tcp'
            }
        ]
    )


def create_ecr_builds_repository():
    ecr_client = boto3.client(
        service_name='ecr',
        region_name=config['instances.region'])
    repository_name = config['images.repository']
    try:
        repository_exists = len(ecr_client.describe_repositories(
            repositoryNames=[repository_name])['repositories']) > 0
    except Exception as e:
        if type(e).__name__ == 'RepositoryNotFoundException':
            repository_exists = False
        else:
            raise e

    if repository_exists:
        print('Repository for builds already exists',
              file=sys.stderr, flush=True)
        return

    print('Creating repository for builds', file=sys.stderr, flush=True)
    ecr_client.create_repository(repositoryName=repository_name)


def _print_bytes_from_docker(json_bytes):
    json_from_docker = json.loads(str(json_bytes, 'utf-8'))
    if 'status' in json_from_docker:
        print(json_from_docker['status'], file=sys.stderr, flush=True)
    if 'progress' in json_from_docker:
        print(json_from_docker['progress'], file=sys.stderr, flush=True)


def pull_common_images():
    # Make sure images are available locally, and that layers are present
    # in the ECR repository
    image_names = ['prodoai/plz_ml-pytorch', 'python:3-slim']
    dependencies: Dependencies = dependencies_from_config(config)
    docker_client: APIClient = docker_client_from_config(config)
    images: ECRImages = dependencies.images

    for image_name in image_names:
        for json_bytes in docker_client.pull(image_name, stream=True):
            _print_bytes_from_docker(json_bytes)
        tag_from_image_name = image_name.replace('/', '-').replace(':', '-')
        docker_client.tag(
            image_name, images.repository, tag=tag_from_image_name)
        images.push(tag_from_image_name, log_level=INFO, log_progress=True)


if __name__ == '__main__':
    root_logger = logging.getLogger()
    root_logger_handler = logging.StreamHandler(stream=sys.stderr)
    root_logger_handler.setFormatter(logging.Formatter(
        '%(asctime)s ' + logging.BASIC_FORMAT))
    root_logger.addHandler(root_logger_handler)
    logging.getLogger('plz').setLevel(INFO)
    create_workers_security_group()
    create_ecr_builds_repository()
    pull_common_images()
else:
    print('You can\'t import this script!', file=sys.stderr)
    exit(1)
