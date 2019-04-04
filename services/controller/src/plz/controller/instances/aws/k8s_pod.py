import io
import logging
from typing import Dict, Iterator, Optional, Tuple

from redis import StrictRedis

from plz.controller.api.exceptions import InstanceStillRunningException
from plz.controller.containers import ContainerState
from plz.controller.instances.instance_base import ExecutionInfo, Instance, \
    Parameters
from plz.controller.results import ResultsStorage

log = logging.getLogger(__name__)


class K8sPod(Instance):

    def __init__(self,
                 redis: StrictRedis,
                 lock_timeout: int,
                 pod_name: str,
                 execution_id: str):
        super().__init__(redis, lock_timeout)
        self.pod_name = pod_name
        self.execution_id = execution_id

    def run(self,
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            docker_run_args: Dict[str, str],
            index_range_to_run: Optional[Tuple[int, int]],
            max_idle_seconds: int = 60 * 30) -> None:
        raise NotImplementedError(
            'run not defined for pods (it\'s the provider that runs an image '
            'creating a pod)')

    def kill(self, force_if_not_idle: bool):
        # TODO: implement
        raise NotImplementedError()

    def get_max_idle_seconds(self) -> int:
        # Doesn't apply to pods
        return 0

    def get_idle_since_timestamp(
            self, container_state: Optional[ContainerState] = None) -> int:
        # Doesn't apply to pods
        return 0

    def get_execution_id(self):
        return self.execution_id

    def get_instance_type(self):
        # TODO: implement later, type of instance (node) the pod is running in
        return 'pod'

    def dispose_if_its_time(
            self, execution_info: Optional[ExecutionInfo] = None) \
            -> Optional[str]:
        # It's never time for a pod
        return None

    def stop_execution(self):
        # TODO: implement later
        raise NotImplementedError()

    def container_state(self) -> Optional[ContainerState]:
        # TODO: implement later (either this or instance state will be
        # meaningful)
        return ContainerState(running=True,
                              status='running',
                              success=False,
                              exit_code=0,
                              finished_at=0)

    def release(self,
                results_storage: ResultsStorage,
                idle_since_timestamp: int,
                release_container: bool = True):
        # TODO: implement later, gather logs, gather output, gather exit
        # status, remove pod
        pass

    def get_resource_state(self) -> str:
        # TODO: check if we care about the state of the pod
        return self.container_state()['status']

    def delete_resource(self) -> None:
        # There is no resource for pods (for EC2 instances, the resource is
        # the actual machine on the cloud)
        pass

    def get_forensics(self) -> dict:
        # TODO: implement later, why did it terminate
        return {}

    @property
    def instance_id(self):
        return self.pod_name

    def get_logs(self, since: Optional[int] = None, stdout: bool = True,
                 stderr: bool = True) -> Iterator[bytes]:
        # TODO: implement later
        yield b'bbbb'

    def get_output_files_tarball(
            self, path: Optional[str], index: Optional[int]) \
            -> Iterator[bytes]:
        # TODO: implement later
        yield b'bbbbb'

    def get_measures_files_tarball(self, index: Optional[int]) \
            -> Iterator[bytes]:
        # TODO: implement later
        yield b'bbbbbb'

    def get_stored_metadata(self) -> dict:
        raise InstanceStillRunningException(self.execution_id)


def get_tag(instance_data, tag, default=None) -> Optional[str]:
    for t in instance_data['Tags']:
        if t['Key'] == tag:
            return t['Value']
    return default


def get_aws_instances(
        client, filters: [(str, str)], only_running: bool) -> [dict]:
    if only_running:
        filters += [('instance-state-name', 'running')]
    return describe_instances(client, filters)


def describe_instances(client, filters) -> [dict]:
    new_filters = [{'Name': n, 'Values': [v]} for (n, v) in filters]
    response = client.describe_instances(Filters=new_filters)
    return [instance
            for reservation in response['Reservations']
            for instance in reservation['Instances']]


class InstanceUnavailableException(Exception):
    pass
