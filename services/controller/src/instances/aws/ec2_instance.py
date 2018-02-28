import socket
from typing import Dict, Optional, List

import invocations
from instances.instance_base import Instance


class EC2Instance(Instance):
    def __init__(self, client, execution_id, data):
        self.client = client
        self.execution_id = execution_id
        self.data = data

    def run(self, command: str, snapshot: str):
        invocations.docker_run(
            self.execution_id, snapshot, command,
            prefix=self._ssh_prefix)

    def logs(self):
        return invocations.docker_logs(
            self.execution_id,
            prefix=self._ssh_prefix)

    def cleanup(self):
        invocations.docker_rm(self.execution_id)

    def set_tags(self, tags):
        instance_id = self.data['InstanceId']
        self.client.create_tags(Resources=[instance_id], Tags=tags)

    @property
    def _ssh_prefix(self):
        ip_address = self.data.get('PublicIpAddress')
        _check_ip(ip_address)
        return [
            'ssh',
            '-o', 'LogLevel=ERROR',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            f'ubuntu@{ip_address}']


class EC2Instances:
    # We find available instances by looking at those in which
    # the Execution-Id tag is empty. The autoscaling group has this tag
    # with an empty value, and it is propagated to new instances.
    _EXECUTION_ID_TAG = 'Execution-Id'

    def __init__(self, client, filters: List[Dict[str, str]]):
        self.client = client
        self.filters = filters

    def instance_for(self, execution_id: str) -> Optional[EC2Instance]:
        response = self.client.describe_instances(
            Filters=self.filters + [
                {'Name': f'tag:{self._EXECUTION_ID_TAG}',
                 'Values': [execution_id]},
            ])
        try:
            return EC2Instance(
                self.client,
                execution_id,
                response['Reservations'][0]['Instances'][0])
        except (KeyError, IndexError):
            return None

    def acquire_for(self, execution_id: str):
        instance = self.instance_for('')
        if instance:
            instance.set_tags([
                {'Key': self._EXECUTION_ID_TAG,
                 'Value': execution_id}
            ])
        return instance

    def release_for(self, execution_id: str):
        self.instance_for(execution_id).cleanup()
        instance = self.instance_for(execution_id)
        if instance:
            instance.set_tags([
                {'Key': self._EXECUTION_ID_TAG,
                 'Value': ''}
            ])
        return instance


def _check_ip(ip: Optional[str]):
    """Throws an exception in the event of a missing or invalid IP address."""
    if ip is None:
        raise ValueError('Expected an IP address, got None')
    try:
        socket.inet_aton(ip)
    except OSError:
        raise ValueError(f'Invalid IP address: [{ip}]')
