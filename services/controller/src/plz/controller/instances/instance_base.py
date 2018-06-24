import io
import logging
from abc import ABC, abstractmethod
from collections import namedtuple
from typing import Any, ContextManager, Dict, Iterator, List, Optional

import time
from redis import StrictRedis
from redis.lock import Lock

from plz.controller.containers import ContainerMissingException, ContainerState
from plz.controller.results.results_base import InstanceStatus, \
    InstanceStatusFailure, InstanceStatusRunning, InstanceStatusSuccess, \
    Results, ResultsStorage

log = logging.getLogger(__name__)

Parameters = Dict[str, Any]
ExecutionInfo = namedtuple(
    'ExecutionInfo',
    ['execution_id', 'running', 'status', 'instance_type', 'max_idle_seconds',
     'idle_since_timestamp', 'instance_id'])


class Instance(Results):
    def __init__(self, redis: StrictRedis):
        self.redis = redis
        # Need to create and memoised the lock afterwards, as we need the
        # AWS instance id and it's not available at this point. Use
        # _redis_lock to access it
        self._memoised_lock = None

    @abstractmethod
    def run(self,
            command: List[str],
            snapshot_id: str,
            parameters: Parameters,
            input_stream: Optional[io.BytesIO],
            docker_run_args: Dict[str, str]) -> None:
        pass

    def get_status(self) -> InstanceStatus:
        state = self.container_state()
        if not state:
            raise InstanceMissingStateException()
        if state.running:
            return InstanceStatusRunning()
        elif state.exit_code == 0:
            return InstanceStatusSuccess()
        else:
            return InstanceStatusFailure(state.exit_code)

    @abstractmethod
    def stop_execution(self):
        pass

    @abstractmethod
    def get_idle_since_timestamp(
            self, container_state: Optional[ContainerState] = None) -> int:
        pass

    @abstractmethod
    def get_execution_id(self) -> str:
        pass

    @abstractmethod
    def get_instance_type(self) -> str:
        pass

    @abstractmethod
    def get_max_idle_seconds(self) -> int:
        pass

    @abstractmethod
    def dispose_if_its_time(
            self, execution_info: Optional[ExecutionInfo] = None):
        # We happen to have the execution info at hand when calling it,
        # and getting the info is not free (queries to the docker server in the
        # workers), so we allow to pass the info as parameter
        pass

    def _is_idle(self, container_state: Optional[ContainerState]) -> bool:
        return self.get_execution_id() == '' or container_state is None

    def get_execution_info(self) -> ExecutionInfo:
        resource_state = self.get_resource_state()
        if resource_state != 'running':
            running = False
            status = resource_state
            idle_since_timestamp = None
        else:
            container_state = self.container_state()
            if self._is_idle(container_state):
                running = False
                status = 'idle'
                idle_since_timestamp = self.get_idle_since_timestamp()
            else:
                running = container_state.running
                status = container_state.status
                idle_since_timestamp = self.get_idle_since_timestamp(
                    container_state)
        return ExecutionInfo(
            instance_type=self.get_instance_type(),
            instance_id=self.instance_id,
            execution_id=self.get_execution_id(),
            running=running,
            status=status,
            idle_since_timestamp=idle_since_timestamp,
            max_idle_seconds=self.get_max_idle_seconds())

    @abstractmethod
    def container_state(self) -> Optional[ContainerState]:
        pass

    @abstractmethod
    def release(self, results_storage: ResultsStorage,
                idle_since_timestamp: int,
                release_container: bool = True) -> bool:
        pass

    @abstractmethod
    def get_resource_state(self) -> str:
        """Get the resource status of the underlying resource (for instance,
           the AWS instance) such as running or terminated"""
        pass

    @abstractmethod
    def delete_resource(self) -> None:
        """Set the underlying resource to not be listed among the live ones"""
        pass

    def harvest(self, results_storage: ResultsStorage):
        with self._lock:
            resource_state = self.get_resource_state()
            execution_id = self.get_execution_id()
            if resource_state == 'terminated':
                try:
                    # Ensure that terminated instances with an execution ID
                    # have results (or a tombstone)
                    if self.get_execution_id() == '':
                        log.warning(
                            'There\'s a terminated instance without an '
                            'execution ID associated.')
                        return
                    with results_storage.get(execution_id) as results:
                        if results is not None:
                            return
                    results_storage.write_tombstone(
                        execution_id,
                        tombstone={'forensics': self.get_forensics()})
                finally:
                    self.delete_resource()

            # We only care about harvesting running and terminated instances
            if resource_state != 'running':
                log.info(f'Instance for execution ID [{execution_id}] is '
                         f'[{resource_state}]')
                return

            try:
                info = self.get_execution_info()
            except ContainerMissingException:
                # The container for an execution can't be found although
                # we have an instance for it. Release the instance without
                # trying to access the container
                log.exception(
                    f'Instance {self.instance_id} for execution ID: '
                    f'{self.get_execution_id()} missing container')
                self.release(
                    results_storage,
                    idle_since_timestamp=int(time.time()),
                    # There's no container so don't try to release things
                    # there
                    release_container=False)
                return
            if info.status == 'exited':
                self.release(results_storage, info.idle_since_timestamp)

            if info.status in {'exited', 'idle'}:
                result = self.dispose_if_its_time(execution_info=info)
                if result is not None:
                    log.error(f'Harvesting: Instance {self.instance_id} for '
                              f'execution ID: {self.get_execution_id()}: '
                              f'{result}')

    def is_terminated(self) -> bool:
        return self.get_resource_state() == 'terminated'

    @abstractmethod
    def kill(self, force_if_not_idle: bool) -> Optional[str]:
        """Kills an instance.

        :param force_if_not_idle: force termination for non-idle instances
        :return: a failure message in case the instance wasn't terminated
        :rtype: Optional[str]
        """
        pass

    @abstractmethod
    def get_forensics(self) -> dict:
        """Gather information useful when the instance is/was misbehaving"""
        pass

    @property
    @abstractmethod
    def instance_id(self) -> str:
        pass

    @property
    def _redis_lock(self) -> Lock:
        if self._memoised_lock is None:
            lock_name = f'lock:{__name__}.{self.__class__.__name__}' + \
                        f'#_lock:{self.instance_id}'
            self._memoised_lock = Lock(self.redis, lock_name)
        return self._memoised_lock

    @property
    def _lock(self):
        return _InstanceContextManager(self._redis_lock)


class InstanceProvider(ABC):
    def __init__(self, results_storage: ResultsStorage):
        self.results_storage = results_storage

    @abstractmethod
    def run_in_instance(self,
                        execution_id: str,
                        command: List[str],
                        snapshot_id: str,
                        parameters: Parameters,
                        input_stream: Optional[io.BytesIO],
                        instance_market_spec: dict,
                        execution_spec: dict) -> Iterator[Dict[str, Any]]:
        pass

    @abstractmethod
    def instance_for(self, execution_id: str) -> Optional[Instance]:
        pass

    def release_instance(
            self, execution_id: str,
            fail_if_not_found: bool=True,
            idle_since_timestamp: Optional[int]=None):
        instance = self.instance_for(execution_id)
        if instance is None:
            if fail_if_not_found:
                raise ValueError(f'Instance for Execution ID {execution_id} ' +
                                 'not found')
            else:
                return
        instance.release(self.results_storage, idle_since_timestamp)

    def kill_instances(
            self, instance_ids: Optional[str], force_if_not_idle: bool) \
            -> None:
        """ Hard stop for a set of instances

        :param instance_ids: instances to dispose of. A value of `None` means
               all instances in the group
        :param force_if_not_idle: force termination for non-idle instances
        :raises: :class:`ProviderKillingInstancesException` if some instances
                 failed to terminate
        :raises: :class:`NoInstancesFound` if asked for the termination of all
                 instances, and there are no instances
        """
        terminate_all_instances = instance_ids is None

        if not terminate_all_instances:
            unprocessed_instance_ids = [i for i in instance_ids]
        else:
            unprocessed_instance_ids = []

        instance_ids_to_messages = {}
        there_is_one_instance = False
        for instance in self.instance_iterator(only_running=False):
            if instance.is_terminated():
                continue
            there_is_one_instance = True
            if terminate_all_instances or instance.instance_id in instance_ids:
                    try:
                        instance.kill(force_if_not_idle)
                    except KillingInstanceException as e:
                        instance_ids_to_messages[instance.instance_id] = \
                            e.message
                    if not terminate_all_instances:
                        unprocessed_instance_ids.remove(instance.instance_id)

        for instance_id in unprocessed_instance_ids:
            instance_ids_to_messages[instance_id] = 'Instance not found'

        if len(instance_ids_to_messages) > 0:
            raise ProviderKillingInstancesException(instance_ids_to_messages)

        if terminate_all_instances and not there_is_one_instance:
            raise NoInstancesFound()

    @abstractmethod
    def push(self, image_tag: str):
        pass

    @abstractmethod
    def instance_iterator(self, only_running: bool) -> Iterator[Instance]:
        pass

    def harvest(self):
        for instance in self.instance_iterator(only_running=False):
            # noinspection PyBroadException
            try:
                instance.harvest(self.results_storage)
            except Exception:
                # Make sure that an exception thrown while harvesting an
                # instance doesn't stop the whole harvesting process
                log.exception('Exception harvesting')

    def get_executions(self) -> [ExecutionInfo]:
        return [
            instance.get_execution_info()
            for instance in self.instance_iterator(only_running=False)
            if not instance.is_terminated()]

    @abstractmethod
    def get_forensics(self, execution_id: str) -> dict:
        """Gather information useful when the instance is/was misbehaving"""
        pass


class InstanceMissingStateException(Exception):
    pass


class NoInstancesFoundException(Exception):
    pass


class KillingInstanceException(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class _InstanceContextManager(ContextManager):
    """
    Allow for the lock to be acquired in several stack frames of the same
    thread
    """
    def __init__(self, instance_lock: Lock):
        self.instance_lock = instance_lock
        self.lock = None

    def acquire(self, blocking=None):
        if self.instance_lock.local.token is None:
            self.instance_lock.acquire(blocking=blocking)
            self.lock = self.instance_lock
        else:
            self.lock = None

    def release(self):
        if self.lock is not None:
            self.lock.release()

    def __enter__(self):
        self.acquire(blocking=True)

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
