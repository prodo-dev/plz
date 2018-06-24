import json
import logging
import os
import random
import uuid
from abc import ABC, abstractmethod
from typing import BinaryIO, Iterator, Optional

import requests
from flask import jsonify, request
from pyhocon import ConfigTree
from redis import StrictRedis

from plz.controller import configuration
from plz.controller.configuration import Dependencies
from plz.controller.db_storage import DBStorage
from plz.controller.exceptions import BadInputMetadataException, \
    ExecutionAlreadyHarvestedException, ExecutionNotFoundException, \
    InstanceStillRunningException, ResponseHandledException
from plz.controller.execution import Executions
from plz.controller.images import Images
from plz.controller.input_data import InputDataConfiguration
from plz.controller.instances.instance_base import Instance, InstanceProvider, \
    NoInstancesFoundException
from plz.controller.types import InputMetadata

JSONString = str


class Controller(ABC):
    @classmethod
    @abstractmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    @abstractmethod
    def ping(self) -> dict:
        pass

    @abstractmethod
    def run_execution(self, command: [str], snapshot_id: str, parameters: dict,
                      instance_market_spec: dict, execution_spec: dict,
                      start_metadata: dict,
                      previous_execution_id: Optional[str] = None) \
            -> Iterator[dict]:
        """:raises IncorrectInputIDException:"""
        pass

    @abstractmethod
    def rerun_execution(
            self, user: str, project: str, previous_execution_id: str,
            instance_market_spec: dict) -> Iterator[dict]:
        pass

    @abstractmethod
    def list_executions(self) -> [dict]:
        pass

    @abstractmethod
    def get_status(self, execution_id: str) -> dict:
        pass

    @abstractmethod
    def get_logs(self, execution_id: str, since: Optional[int]) \
            -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_output_files(self, execution_id: str) -> Iterator[bytes]:
        pass

    @abstractmethod
    def get_measures(
            self, execution_id: str, summary: bool) -> Iterator[JSONString]:
        pass

    @abstractmethod
    def delete_execution(self, execution_id: str, fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        """:raises InstanceStillRunningException:
           :raises ExecutionAlreadyHarvestedException:"""
        pass

    @abstractmethod
    def get_history(self, user: str, project: str) -> Iterator[JSONString]:
        pass

    @abstractmethod
    def create_snapshot(self, image_metadata: dict, context: BinaryIO) \
            -> Iterator[JSONString]:
        pass

    @abstractmethod
    def put_input(self, input_id: str, input_metadata: InputMetadata,
                  input_data_stream: BinaryIO) -> None:
        pass

    @abstractmethod
    def check_input_data(
            self, input_id: str, metadata: InputMetadata) -> bool:
        pass

    @abstractmethod
    def get_input_id_or_none(self, metadata: InputMetadata) -> Optional[str]:
        pass

    @abstractmethod
    def delete_input_data(self, input_id: str):
        pass

    @abstractmethod
    def get_user_last_execution_id(self, user: str) -> Optional[str]:
        pass

    @abstractmethod
    def kill_instances(
            self, instance_ids: Optional[str], force_if_not_idle: bool) -> bool:
        """:raises ProviderKillingInstancesException:

           :returns bool: false if there are no instances to kill
        """
        pass

    @abstractmethod
    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        pass


class ControllerImpl(Controller):
    def __init__(self, config: ConfigTree, log: logging.Logger):
        self.port = config.get_int('port', 8080)
        dependencies: Dependencies = configuration.dependencies_from_config(
            config)
        self.images: Images = dependencies.images
        self.instance_provider: InstanceProvider = \
            dependencies.instance_provider
        self.db_storage: DBStorage = dependencies.db_storage
        self.redis: StrictRedis = dependencies.redis
        self.executions: Executions = Executions(
            dependencies.results_storage, self.instance_provider)
        data_dir = config['data_dir']
        input_dir = os.path.join(data_dir, 'input')
        temp_data_dir = os.path.join(data_dir, 'tmp')
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(temp_data_dir, exist_ok=True)
        self.input_data_configuration = InputDataConfiguration(
            self.redis, input_dir=input_dir, temp_data_dir=temp_data_dir)
        self.log = log

    def ping(self) -> dict:
        # This is plz, and we're up and running
        return {'plz': 'pong'}

    def run_execution(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            previous_execution_id: Optional[str] = None) -> Iterator[dict]:
        execution_id = str(_get_execution_uuid())
        start_metadata['command'] = command
        start_metadata['snapshot_id'] = snapshot_id
        start_metadata['parameters'] = parameters
        start_metadata['instance_market_spec'] = instance_market_spec
        start_metadata['execution_spec'] = {
            k: v for k, v in execution_spec.items()
            if k not in {'user', 'project'}}
        start_metadata['user'] = execution_spec['user']
        start_metadata['project'] = execution_spec['project']
        start_metadata['previous_execution_id'] = previous_execution_id
        self.db_storage.store_start_metadata(execution_id, start_metadata)

        yield {'id': execution_id}

        try:
            input_stream = self.input_data_configuration.prepare_input_stream(
                execution_spec)
            startup_statuses = self.instance_provider.run_in_instance(
                execution_id, command, snapshot_id, parameters,
                input_stream, instance_market_spec, execution_spec)
            instance: Optional[Instance] = None
            for status in startup_statuses:
                if 'message' in status:
                    yield {'status': status['message']}
                if 'instance' in status:
                    instance = status['instance']
            if instance is None:
                yield {'error': 'Couldn\'t get an instance.'}
                return
            self._set_user_last_execution_id(
                execution_spec['user'], execution_id)
        except Exception as e:
            self.log.exception('Exception running command.')
            yield {'error': str(e)}

    def rerun_execution(
            self, user: str, project: str, previous_execution_id: str,
            instance_market_spec: dict) -> Iterator[dict]:
        start_metadata = self.db_storage.retrieve_start_metadata(
            previous_execution_id)

        command = start_metadata['command']
        snapshot_id = start_metadata['snapshot_id']
        parameters = start_metadata['parameters']
        execution_spec = start_metadata['execution_spec']
        execution_spec['user'] = user
        execution_spec['project'] = project
        return self.run_execution(
            command, snapshot_id, parameters, instance_market_spec,
            execution_spec, start_metadata, previous_execution_id)

    def list_executions(self) -> [dict]:
        # It's not protected, it's preceded by underscore as to avoid
        # name conflicts, see docs
        # noinspection PyProtectedMember
        return [info._asdict()
                for info in self.instance_provider.get_executions()]

    def harvest(self) -> None:
        self.instance_provider.harvest()

    def get_status(self, execution_id: str) -> dict:
        return self.executions.get(execution_id).get_status()

    def get_logs(self, execution_id: str, since: Optional[int]) \
            -> Iterator[bytes]:
        return self.executions.get(execution_id).get_logs(since=since)

    def get_output_files(self, execution_id: str) -> Iterator[bytes]:
        return self.executions.get(execution_id).get_output_files_tarball()

    def get_measures(self, execution_id: str, summary: bool) \
            -> Iterator[JSONString]:
        measures = self.executions.get(execution_id).get_measures()
        if summary:
            measures_to_return = measures.get('summary', {})
        else:
            measures_to_return = measures
        if measures_to_return == {}:
            return []
        # We return text that happens to be json, as we want the cli to show it
        # indented properly and we don't want an additional conversion round
        # json <-> str.
        # In the future we can have another entrypoint or a parameter
        # to return the json if we use it programmatically in the CLI.
        str_response = json.dumps(measures_to_return, indent=2) + '\n'
        for l in str_response.splitlines(keepends=True):
            yield l

    def delete_execution(self, execution_id: str, fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        response = jsonify({})
        status = self.executions.get(execution_id).get_status()
        if fail_if_running and status.running:
            raise InstanceStillRunningException(execution_id=execution_id)
        instance = self.instance_provider.instance_for(execution_id)
        if fail_if_deleted and instance is None:
            raise ExecutionAlreadyHarvestedException(execution_id)
        self.instance_provider.release_instance(
            execution_id, fail_if_not_found=False)
        response.status_code = requests.codes.no_content
        return response

    def get_history(self, user: str, project: str) -> Iterator[JSONString]:
        execution_ids = self.db_storage.retrieve_finished_execution_ids(
            user, project)

        yield '{\n'
        first = True
        for execution_id in execution_ids:
            if not first:
                yield ',\n'
            first = False
            yield f'"{execution_id}": ' \
                  f'{self.executions.get(execution_id).get_metadata()}'
        yield '\n}\n'

    def create_snapshot(self, image_metadata: dict, context: BinaryIO) -> \
            Iterator[JSONString]:
        tag = Images.construct_tag(image_metadata)
        yield from (
            frag.decode('utf-8') for frag in self.images.build(context, tag))
        self.instance_provider.push(tag)
        yield json.dumps({'id': tag})

    def put_input(self, input_id: str, input_metadata: InputMetadata,
                  input_data_stream: BinaryIO) -> None:
        if not input_metadata.has_all_args_or_none():
            raise BadInputMetadataException(input_metadata.__dict__)
        self.input_data_configuration.publish_input_data(
            input_id, input_metadata, request.stream)
        return jsonify({'id': input_id})

    def check_input_data(self, input_id: str,
                         input_metadata: InputMetadata) -> bool:
        if not input_metadata.has_all_args_or_none():
            raise BadInputMetadataException(input_metadata.__dict__)
        return self.input_data_configuration.check_input_data(
            input_id, input_metadata)

    def get_input_id_or_none(
            self, input_metadata: InputMetadata) -> Optional[str]:
        if not input_metadata.has_all_args_or_none():
            raise BadInputMetadataException(input_metadata.__dict__)
        id_or_none = \
            self.input_data_configuration.get_input_id_from_metadata_or_none(
                input_metadata)
        return id_or_none

    def delete_input_data(self, input_id: str):
        try:
            os.remove(self.input_data_configuration.input_file(input_id))
        except FileNotFoundError:
            pass

    def get_user_last_execution_id(self, user: str) -> Optional[str]:
        execution_id_bytes = self.redis.get(
            f'key:{__name__}#user_last_execution_id:{user}')
        if execution_id_bytes:
            return str(execution_id_bytes, encoding='utf-8')
        else:
            return None

    def kill_instances(self, instance_ids: Optional[str],
                       force_if_not_idle: bool) -> bool:
        try:
            self.instance_provider.kill_instances(
                instance_ids=instance_ids, force_if_not_idle=force_if_not_idle)
        except NoInstancesFoundException:
            return False

    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        start_metadata = self.db_storage.retrieve_start_metadata(execution_id)
        if start_metadata is None:
            raise ExecutionNotFoundException(execution_id)
        return {'start_metadata': start_metadata}

    @classmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    def _set_user_last_execution_id(self, user: str, execution_id: str) -> None:
        self.redis.set(f'key:{__name__}#user_last_execution_id:{user}',
                       execution_id)


def _get_execution_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))
