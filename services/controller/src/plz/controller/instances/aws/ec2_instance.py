import io
import logging
import os.path
import time
from typing import Dict, Iterator, Optional, Tuple

from redis import StrictRedis

from plz.controller.containers import ContainerState, Containers
from plz.controller.images import Images
from plz.controller.instances.docker import DockerInstance
from plz.controller.instances.instance_base import ExecutionInfo, Instance, \
    KillingInstanceException, Parameters
from plz.controller.results import ResultsStorage
from plz.controller.volumes import Volumes

log = logging.getLogger(__name__)


class EC2Instance(Instance):
    ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')

    # We find available instances by looking at those in which
    # the Execution-Id tag is the empty string and they are not earmarked (they
    # haven't been started for a particular execution ID). Instances are
    # started with an empty value for the execution ID, the tag is set
    # when the instance starts executing, and it's emptied again
    # when the execution finishes. Also, at start the Earmark-Execution-Id
    # is set to the execution ID that the instance is being started for, so
    # that it's not picked up when starting other executions. The
    # earmark is set to empty when the Execution-Id tag is set. When an
    # execution finishes, both the Execution-Id and the
    # Earmark-Execution-Id tags are empty, and instances can be reused by
    # other executions (or be disposed of by harvesting if the time has come)
    EXECUTION_ID_TAG = 'Plz:Execution-Id'
    GROUP_NAME_TAG = 'Plz:Group-Id'
    MAX_IDLE_SECONDS_TAG = 'Plz:Max-Idle-Seconds'
    IDLE_SINCE_TIMESTAMP_TAG = 'Plz:Idle-Since-Timestamp'
    EARMARK_EXECUTION_ID_TAG = 'Plz:Earmark-Execution-Id'

    def __init__(self,
                 client,
                 images: Images,
                 containers: Containers,
                 volumes: Volumes,
                 container_execution_id: str,
                 data: dict,
                 redis: StrictRedis,
                 lock_timeout: int,
                 container_idle_timestamp_grace: int):
        super().__init__(redis, lock_timeout)
        self.client = client
        self.images = images
        self.delegate = DockerInstance(
            images, containers, volumes, container_execution_id, redis,
            lock_timeout)
        self.data = data
        self.container_idle_timestamp_grace = container_idle_timestamp_grace

    def run(self,
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            docker_run_args: Dict[str, str],
            index_range_to_run: Optional[Tuple[int, int]],
            max_idle_seconds: int = 60 * 30) -> None:
        # Sanity check before we get the lock
        if self._get_earmark() != self.delegate.execution_id:
            raise InstanceUnavailableException(
                'Trying to run in an instance that is not earmarked for this '
                'execution!')
        with self._lock:
            # Must be earmarked for this run
            if not self._is_running_and_free(
                    earmark=self.delegate.execution_id,
                    earmark_optional=False,
                    check_running=True):
                raise InstanceUnavailableException(
                    f'Instance {self.instance_id} cannot execute '
                    f'{self.delegate.execution_id} as it\'s not '
                    f'free (executing [{self.get_execution_id()}] '
                    f'or earmarked for [{self._get_earmark()}] or '
                    f'not running)')
            self.images.pull(snapshot_id)
            self.delegate.run(snapshot_id, parameters, input_stream,
                              docker_run_args, index_range_to_run)
            self._set_execution_id(
                self.delegate.execution_id, max_idle_seconds)

    def is_up(self, is_instance_newly_created: bool):
        if not self._is_running():
            return False
        return self.images.can_pull(
            5 if is_instance_newly_created else 1)

    def kill(self, force_if_not_idle: bool):
        if not force_if_not_idle and not self._is_idle(
                self.container_state()):
            raise KillingInstanceException('Instance is not idle')
        try:
            self.client.terminate_instances(InstanceIds=[self.instance_id])
        except Exception as e:
            raise KillingInstanceException(str(e)) from e

    def earmark_for(
            self, execution_id: str,
            instance_max_startup_time_in_minutes: int) -> None:
        if self._get_earmark() == execution_id:
            return
        # To be on the safe side, we assume that if the instance is locked
        # then it's not free as to be earmarked for an instance (someone is
        # doing something to it)
        lock = self._lock
        acquired = lock.acquire(blocking=False)
        try:
            if not acquired or not self._is_running_and_free(
                    earmark=execution_id, check_running=False,
                    earmark_optional=True):
                raise InstanceUnavailableException(
                    f'Cannot earmark {self.instance_id} for '
                    f'{execution_id} as it\'s not '
                    f'free (executing [{self.get_execution_id()}] or locked '
                    f'({not acquired}) or earmarked for '
                    f'[{self._get_earmark()}]')
            self._set_tags([
                {'Key': EC2Instance.EARMARK_EXECUTION_ID_TAG,
                 'Value': execution_id},
                {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
                 'Value': str(60 * instance_max_startup_time_in_minutes)}])
        finally:
            if acquired:
                lock.release()

    def unearmark_for(self, execution_id: str) -> None:
        """
        If the instance is earmarked for this execution ID, remove the earmark
        """
        # Do not hold the lock if we aren't doing anything
        if self._get_earmark() != execution_id:
            return
        with self._lock:
            self._do_unearmark()

    class HardUnearmarkException(Exception):
        pass

    def hard_unearmark_for(self, execution_id: str) -> None:
        """
        If the instance is earmarked for this execution ID, remove the earmark

        Do not lock the instance, just do it. To be used for error handling
        """
        # Rationale for this method:
        # By not getting the lock, we might might get into a race condition
        # with another thread earmarking, and potentially voiding its
        # earmark. The worst thing that can happen is that, when the thread
        # is ready to run, it checks the earmark and doesn't run as the
        # earmark is gone. It'll retry, again, possibly finding this very
        # instance, or another suitable one that is free

        # Do nothing if the instance is not earmarked for this execution
        if self._get_earmark() != execution_id:
            return
        log.warning(f'Hard unearmarking instance {self.instance_id} '
                    f'for execution {execution_id}')
        self._do_unearmark()

    def _do_unearmark(self):
        self._set_tags([
            {'Key': EC2Instance.EARMARK_EXECUTION_ID_TAG,
             'Value': ''}])

    def _set_execution_id(
            self, execution_id: str, max_idle_seconds: int):
        self._set_tags([
            {'Key': EC2Instance.EXECUTION_ID_TAG,
             'Value': execution_id},
            {'Key': EC2Instance.MAX_IDLE_SECONDS_TAG,
             'Value': str(max_idle_seconds)}])
        self._do_unearmark()

    def _get_earmark(self):
        return get_tag(self.data, EC2Instance.EARMARK_EXECUTION_ID_TAG)

    def _set_tags(self, tags):
        instance_id = self.instance_id
        self.client.create_tags(Resources=[instance_id], Tags=tags)
        self.data = describe_instances(
            self.client, [('instance-id', instance_id)])[0]

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
            self, execution_info: Optional[ExecutionInfo] = None) \
            -> Optional[str]:
        if execution_info is not None:
            ei = execution_info
        else:
            ei = self.get_execution_info()

        now = int(time.time())

        if ei.idle_since_timestamp > now:
            log.warning('Instance has been idle since a '
                        f'time {ei.idle_since_timestamp} later than the'
                        f'current one {now}. If this gap is bigger than '
                        f'{self.container_idle_timestamp_grace} the instance '
                        f'will be disposed of')

        graced_timestamp = ei.idle_since_timestamp - \
            self.container_idle_timestamp_grace
        # In weird cases just dispose as well
        if now - ei.idle_since_timestamp > ei.max_idle_seconds or \
                graced_timestamp > now or \
                ei.max_idle_seconds <= 0:
            log.info(f'Disposing of instance {self.instance_id}. Now: {now}.'
                     f'Idle since: {ei.idle_since_timestamp}. '
                     f'Max idle seconds: {ei.max_idle_seconds}')
            # We check that it's idle. That should be the case as the lock is
            # held and this method is called after the execution ID for the
            # instance was set to the empty string. But, y'know, computers...
            result = self.kill(force_if_not_idle=False)
            return result

        return None

    def stop_execution(self):
        return self.delegate.stop_execution()

    def container_state(self) -> Optional[ContainerState]:
        if self.get_resource_state() != 'running':
            # Do not try to get a container for instances that are pending,
            # shutting down, etc.
            return None
        return self.delegate.container_state()

    def release(self,
                results_storage: ResultsStorage,
                idle_since_timestamp: int,
                release_container: bool = True):
        with self._lock:
            self.delegate.release(
                results_storage, idle_since_timestamp, release_container)
            self._set_tags([
                {'Key': EC2Instance.EXECUTION_ID_TAG,
                 'Value': ''},
                {'Key': EC2Instance.IDLE_SINCE_TIMESTAMP_TAG,
                 'Value': str(idle_since_timestamp)}])

    def _is_running_and_free(self, earmark: str,
                             check_running: bool,
                             earmark_optional: bool):
        if check_running and not self._is_running():
            return False
        if earmark_optional:
            instances = get_aws_instances(
                self.client,
                only_running=check_running,
                filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                         (f'tag:{EC2Instance.EARMARK_EXECUTION_ID_TAG}', ''),
                         ('instance-id', self.instance_id)])
            if len(instances) > 0:
                return True
        instances = get_aws_instances(
            self.client,
            only_running=check_running,
            filters=[(f'tag:{EC2Instance.EXECUTION_ID_TAG}', ''),
                     (f'tag:{EC2Instance.EARMARK_EXECUTION_ID_TAG}',
                      earmark),
                     ('instance-id', self.instance_id)])
        return len(instances) > 0

    def _is_running(self):
        instances = get_aws_instances(
            self.client,
            only_running=True,
            filters=[('instance-id', self.instance_id)])
        return len(instances) > 0

    def get_resource_state(self) -> str:
        instance = describe_instances(
            self.client,
            filters=[('instance-id', self.instance_id)])[0]
        return instance['State']['Name']

    def delete_resource(self) -> None:
        # It seems AWS doesn't allow to delete an instance. We set the group
        # tag to empty so it won't be listed for a group anymore.
        self._set_tags([{'Key': EC2Instance.GROUP_NAME_TAG,
                         'Value': ''}])

    def get_forensics(self) -> dict:
        spot_requests = self.client.describe_spot_instance_requests(
            Filters=[{'Name': 'instance-id',
                      'Values': [self.instance_id]}])['SpotInstanceRequests']
        if len(spot_requests) == 0:
            spot_request_info = {}
        elif len(spot_requests) > 1:
            spot_request_info = {}
            log.warning('More than one spot request for instance '
                        f'{self.instance_id}')
        else:
            spot_request_info = spot_requests[0]
        return {'SpotInstanceRequest': spot_request_info,
                'InstanceState': self.get_resource_state()}

    @property
    def instance_id(self):
        return self.data['InstanceId']

    def get_logs(self, since: Optional[int] = None, stdout: bool = True,
                 stderr: bool = True) -> Iterator[bytes]:
        return self.delegate.get_logs(
            since=since, stdout=stdout, stderr=stderr)

    def get_output_files_tarball(
            self, path: Optional[str], index: Optional[int]) \
            -> Iterator[bytes]:
        return self.delegate.get_output_files_tarball(path, index)

    def get_measures_files_tarball(self, index: Optional[int]) \
            -> Iterator[bytes]:
        return self.delegate.get_measures_files_tarball(index)

    def get_stored_metadata(self) -> dict:
        return self.delegate.get_stored_metadata()


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
