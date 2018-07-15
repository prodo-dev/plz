import boto3
import sys

from plz.controller import configuration

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
        print('Security group for workers already exists')
        return

    print('Creating security group for workers')

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
    try:
        repository_exists = len(ecr_client.describe_repositories(
            repositoryNames=[repository_name])['images.repositories']) > 0
    except Exception as e:
        if type(e).__name__ == 'RepositoryNotFoundException':
            repository_exists = False
        else:
            raise e

    if repository_exists:
        print('Repository for builds already exists')
        return

    print('Creating repository for builds')
    ecr_client.create_repository(repositoryName=repository_name)


if __name__ == '__main__':
    create_workers_security_group()
    create_ecr_builds_repository()
else:
    print('You can\'t import this script!', file=sys.stderr)
    exit(1)
