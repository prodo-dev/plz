import io
import logging
import os.path
import time
from typing import Iterator, List, Optional, Dict

from redis import StrictRedis

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base \
    import ExecutionInfo, Instance, Parameters
from plz.controller.results import ResultsStorage
from plz.controller.volumes import Volumes

log = logging.getLogger(__name__)


class EC2Instance(Instance):
    ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')

    # We find available instances by looking at those in which
    # the Execution-Id tag is the empty string. Instances are
    # started with an empty value for this tag, the tag is set
    # when the instance starts executing, and it's emptied again
    # when the execution finishes
    EXECUTION_ID_TAG = 'Plz:Execution-Id'
    GROUP_NAME_TAG = 'Plz:Group-Id'
    MAX_IDLE_SECONDS_TAG = 'Plz:Max-Idle-Seconds'
    IDLE_SINCE_TIMESTAMP_TAG = 'Plz:Idle-Since-Timestamp'

    def __init__(self,
                 client,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 execution_id: str,
                 data: dict,
                 redis: StrictRedis):
        super().__init__(redis)
        self.client = client
        self.images = images
        self.delegate = DockerInstance(
            images, containers, volumes, execution_id, redis)
        self.data = data

    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            docker_run_args: Dict[str, str]):
        self.images.pull(snapshot_id)
        self.delegate.run(command, snapshot_id, parameters, input_stream,
                          docker_run_args)

    def logs(self, since: Optional[int],
             stdout: bool = True, stderr: bool = True) -> Iterator[bytes]:
        return self.delegate.logs(
            since=since, stdout=stdout, stderr=stderr)

    def is_up(self, is_instance_newly_created: bool):
        return self.images.can_pull(
            5 if is_instance_newly_created else 1)

    def output_files_tarball(self) -> Iterator[bytes]:
        return self.delegate.output_files_tarball()

    def _dispose(self):
        self.client.terminate_instances(InstanceIds=[self._instance_id])

    def set_execution_id(
            self, execution_id: str, max_idle_seconds: int) -> bool:
        with self._lock:
            if not self._is_free():
                return False
            if not self.delegate.set_execution_id(
                    execution_id, max_idle_seconds, _lock_held=True):
                return False
            self._set_tags([
                {'Key': EC2Instance.EXECUTION_ID_TAG,
                 'Value': execution_id},
                {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                 'Value': str(max_idle_seconds)}
            ])
            return True

    def _set_tags(self, tags):
        instance_id = self._instance_id
        self.client.create_tags(Resources=[instance_id], Tags=tags)
        response = self.client.describe_instances(
            Filters=[{'Name': 'instance-id',
                      'Values': [instance_id]}])
        self.data = [instance
                     for reservation in response['Reservations']
                     for instance in reservation['Instances']][0]

    def get_max_idle_seconds(self) -> int:
        return int(get_tag(
            self.data, self.MAX_IDLE_SECONDS_TAG, '0'))

    def get_idle_since_timestamp(
            self, container_state: Optional[ContainerState] = None) -> int:
        if container_state is not None:
            return container_state.finished_at
        return int(get_tag(
            self.data, self.IDLE_SINCE_TIMESTAMP_TAG, '0'))

    def get_execution_id(self):
        return get_tag(
            self.data, self.EXECUTION_ID_TAG, '')

    def get_instance_type(self):
        return self.data['InstanceType']

    def dispose_if_its_time(
            self, execution_info: Optional[ExecutionInfo] = None):
        if execution_info is not None:
            ei = execution_info
        else:
            ei = self.get_execution_info()

        status = ei.status
        if status != 'exited' and status != 'idle':
            return

        now = int(time.time())
        # In weird cases just dispose as well
        if now - ei.idle_since_timestamp > ei.max_idle_seconds or \
                ei.idle_since_timestamp > now or \
                ei.max_idle_seconds < 0:
            self._dispose()

    def stop_execution(self):
        return self.delegate.stop_execution()

    def container_state(self) -> Optional[dict]:
        return self.delegate.container_state()

    def release(self,
                results_storage: ResultsStorage,
                idle_since_timestamp: int,
                _lock_held: bool=False):
        if _lock_held:
            self._do_release(results_storage, idle_since_timestamp)
        else:
            with self._lock:
                self._do_release(results_storage, idle_since_timestamp)

    def _do_release(self, results_storage, idle_since_timestamp):
        self.delegate.release(
            results_storage, idle_since_timestamp, _lock_held=True)
        self._set_tags([
            {'Key': EC2Instance.EXECUTION_ID_TAG,
             'Value': ''},
            {'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
             'Value': str(idle_since_timestamp)}])

    def _is_free(self):
        instances = get_running_aws_instances(
            self.client,
            filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                     ('instance-id', self._instance_id)])
        return len(instances) > 0

    @property
    def _instance_id(self):
        return self.data['InstanceId']


def get_tag(instance_data, tag, default=None) -> Optional[str]:
    for t in instance_data['Tags']:
        if t['Key'] == tag:
            return t['Value']
    return default


def get_running_aws_instances(client, filters: [(str, str)]):
    new_filters = [{'Name': n, 'Values': [v]} for (n, v) in filters]
    instance_state_filter = [{'Name': 'instance-state-name',
                              'Values': ['running']}]
    response = client.describe_instances(
        Filters=new_filters + instance_state_filter)
    return [instance
            for reservation in response['Reservations']
            for instance in reservation['Instances']]
