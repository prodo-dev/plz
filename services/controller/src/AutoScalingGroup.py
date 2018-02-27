# coding=utf-8

import threading
import time
from typing import Iterator, Optional, Union

import boto3
from botocore.exceptions import ClientError


class MaxNumberOfInstancesReached(Exception):
    pass


class AutoScalingGroup:
    # We find available instances by looking at those in which
    # the Execution-Id tag is empty. The autoscaling group has this tag
    # with an empty value, and it is propagated to new instances.
    _EXECUTION_ID_TAG = 'Execution-Id'

    _name_to_group = {}
    _name_to_group_lock = threading.RLock()

    def __new__(cls, name: str):
        with AutoScalingGroup._name_to_group_lock:
            try:
                return AutoScalingGroup._name_to_group[name]
            except KeyError:
                pass
            AutoScalingGroup.check_autoscaling_group_exists(name)
            group = super().__new__(cls)
            AutoScalingGroup._name_to_group[name] = group
            return group

    def __init__(self, name: str):
        self.name = name
        self.auto_scaling_client = boto3.client('autoscaling')
        self.ec2_client = boto3.client('ec2')
        self.lock = threading.RLock()

    @staticmethod
    def check_autoscaling_group_exists(name: str):
        client = boto3.client('autoscaling')
        response = client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[name],
            MaxRecords=1
        )
        if len(response['AutoScalingGroups']) == 0:
            raise ValueError(f'Auto scaling group doesn\'t exist: [{name}]')

    def get_desired_capacity(self) -> int:
        response = self.auto_scaling_client.describe_auto_scaling_groups(
            AutoScalingGroupNames=[self.name],
            MaxRecords=1
        )
        return int(response['AutoScalingGroups'][0]['DesiredCapacity'])

    def _increase_desired_capacity(self, amount=1):
        with self.lock:
            desired_capacity = self.get_desired_capacity()
            self.auto_scaling_client.set_desired_capacity(
                AutoScalingGroupName=self.name,
                DesiredCapacity=desired_capacity + amount,
                HonorCooldown=True)

    def _get_available_instance(self):
        return self.get_instance_from_execution_id('')

    @staticmethod
    def get_public_ip_of_instance(instance: dict):
        return instance['PublicIpAddress']

    def get_instance_from_execution_id(
            self, execution_id_tag) -> Optional[dict]:
        response = self.ec2_client.describe_instances(
            Filters=[
                {'Name': f'tag:{self._EXECUTION_ID_TAG}',
                 'Values': [execution_id_tag]},
                {'Name': 'tag:aws:autoscaling:groupName',
                 'Values': [self.name]}])
        for reservation in response['Reservations']:
            try:
                return reservation['Instances'][0]
            except KeyError or IndexError:
                pass
        return None

    def _set_execution_id_tag(self, instance_id: str, execution_id: str):
        self.ec2_client.create_tags(
            Resources=[instance_id],
            Tags=[{'Key': self._EXECUTION_ID_TAG,
                   'Value': execution_id}]
        )

    def execution_finished(self, execution_id: str):
        self._set_execution_id_tag(
            self.get_instance_from_execution_id(execution_id)['InstanceId'],
            '')

    def get_available_instance_for_execution(
            self,
            execution_id: str,
            max_trials: int = 30,
            wait_for_seconds: int = 10) \
            -> Iterator[Union[str, dict]]:
        """
        Gets an available instance for the execution with the given id.

        If there's at least one instance in the group that is not running
        a command, assign the execution id to one of them and return it.
        Otherwise, increase the desired capacity of the group and try until
        the maximum number of trials.

        :return: the dict of the instance, as returned by boto, or None
                 if unsuccessful
        """
        tries_remaining = max_trials
        with self.lock:
            did_increase_capacity = False
            while tries_remaining > 0:
                tries_remaining -= 1

                if not did_increase_capacity:
                    try:
                        self._increase_desired_capacity()
                        did_increase_capacity = True
                        yield 'allocated'
                    except ClientError as e:
                        error_code = e.response['Error']['Code']
                        # Might fail if there's a scaling event
                        # taking place
                        if error_code == 'ScalingActivityInProgress':
                            pass
                        elif error_code == 'ValidationError':
                            raise MaxNumberOfInstancesReached(e.args)
                        else:
                            raise

                time.sleep(wait_for_seconds)

                instance = self._get_available_instance()

                if instance is not None:
                    yield 'started'
                    self.ec2_client.create_tags(
                        Resources=[instance['InstanceId']],
                        Tags=[
                            {'Key': self._EXECUTION_ID_TAG,
                             'Value': execution_id}
                        ]
                    )
                    yield instance
                    break

                yield 'pending'
