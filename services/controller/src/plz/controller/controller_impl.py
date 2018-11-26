import json
import logging
import os
import random
import uuid
from copy import deepcopy
from typing import BinaryIO, Iterator, List, Optional, Tuple

import requests
from flask import jsonify, request
from pyhocon import ConfigTree
from redis import StrictRedis

from plz.controller import configuration
from plz.controller.api.controller import Controller
from plz.controller.api.exceptions import BadInputMetadataException, \
    ExecutionAlreadyHarvestedException, ExecutionNotFoundException, \
    InstanceStillRunningException, ResponseHandledException
from plz.controller.api.types import InputMetadata, JSONString
from plz.controller.configuration import Dependencies
from plz.controller.db_storage import DBStorage
from plz.controller.execution import Executions
from plz.controller.execution_composition import AtomicComposition, \
    IndicesComposition
from plz.controller.images import Images
from plz.controller.input_data import InputDataConfiguration
from plz.controller.instances.instance_base import Instance, \
    InstanceProvider, NoInstancesFoundException


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

    # noinspection PyMethodMayBeStatic
    def ping(self,
             ping_timeout: int,
             build_timestamp: Optional[int] = None) -> dict:
        # This is plz, and we're up and running
        return {
            # This is plz, and we're up and running
            'plz': 'pong',
            'build_timestamp': build_timestamp
        }

    def run_execution(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            parallel_indices_range: Optional[Tuple[int, int]],
            indices_per_execution: Optional[int]) \
            -> Iterator[dict]:
        return self._do_run_execution(
            command, snapshot_id, parameters, instance_market_spec,
            execution_spec, start_metadata,
            parallel_indices_range=parallel_indices_range,
            indices_per_execution=indices_per_execution,
            previous_execution_id=None)

    def rerun_execution(
            self, user: str, project: str,
            instance_max_uptime_in_minutes: Optional[int],
            override_parameters: Optional[dict],
            previous_execution_id: str,
            instance_market_spec: dict) -> Iterator[dict]:
        start_metadata = self.db_storage.retrieve_start_metadata(
            previous_execution_id)

        command = start_metadata['command']
        snapshot_id = start_metadata['snapshot_id']
        if override_parameters is not None:
            parameters = override_parameters
            start_metadata['parameters'] = override_parameters
        else:
            parameters = start_metadata['parameters']
        execution_spec = start_metadata['execution_spec']
        execution_spec['user'] = user
        execution_spec['project'] = project
        execution_spec['instance_max_uptime_in_minutes'] = \
            instance_max_uptime_in_minutes
        return self._do_run_execution(
            command, snapshot_id, parameters, instance_market_spec,
            execution_spec, start_metadata,
            parallel_indices_range=start_metadata.get(
                'parallel_indices_range'),
            indices_per_execution=start_metadata.get('indices_per_execution'),
            previous_execution_id=previous_execution_id)

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

    def get_output_files(
            self, execution_id: str, path: Optional[str],
            index: Optional[str]) -> Iterator[bytes]:
        return self.executions.get(execution_id).get_output_files_tarball(
            path, index)

    def get_measures(self, execution_id: str, summary: bool,
                     index: Optional[int]) -> Iterator[JSONString]:
        measures = self.executions.get(execution_id).get_measures(index)
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
            metadata = self.executions.get(execution_id).get_metadata()
            yield f'"{execution_id}": {json.dumps(metadata)}'
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

    def kill_instances(self, instance_ids: Optional[List[str]],
                       force_if_not_idle: bool) -> bool:
        try:
            self.instance_provider.kill_instances(
                instance_ids=instance_ids, force_if_not_idle=force_if_not_idle)
            return True
        except NoInstancesFoundException:
            return False

    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        start_metadata = self.db_storage.retrieve_start_metadata(execution_id)
        if start_metadata is None:
            raise ExecutionNotFoundException(execution_id)
        return {'start_metadata': start_metadata}

    def get_execution_composition(self, execution_id: str) -> dict:
        composition = self.db_storage.retrieve_execution_composition(
            execution_id)
        return composition.to_jsonable_dict()

    @classmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    def _set_user_last_execution_id(self, user: str, execution_id: str) \
            -> None:
        self.redis.set(f'key:{__name__}#user_last_execution_id:{user}',
                       execution_id)

    def _do_run_execution(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            parallel_indices_range: Optional[Tuple[int, int]],
            indices_per_execution: Optional[int],
            previous_execution_id: Optional[str]) -> Iterator[dict]:
        execution_id = str(_get_execution_uuid())

        metadatas = self._store_metadata_for_all_executions(
            command, snapshot_id, parameters, instance_market_spec,
            execution_spec, start_metadata, parallel_indices_range,
            indices_per_execution, previous_execution_id, execution_id)

        self._set_user_last_execution_id(
            execution_spec['user'], execution_id)
        yield {'id': execution_id}

        try:
            input_stream = self.input_data_configuration.prepare_input_stream(
                execution_spec)

            def status_generator(ex_id: str, ex_spec: dict) -> Iterator[dict]:
                return self.instance_provider.run_in_instance(
                    ex_id, command, snapshot_id, parameters,
                    input_stream, instance_market_spec, ex_spec)

            statuses_generators = [
                status_generator(m['execution_id'], m['execution_spec'])
                for m in metadatas
            ]

            instances = [None for _ in statuses_generators]

            yield from _assign_instances(instances, parallel_indices_range,
                                         statuses_generators)

            if parallel_indices_range is None:
                if instances[0] is None:
                    yield {'error': 'Couldn\'t get an instance.'}
                    return
                composition = AtomicComposition(execution_id)
            else:
                indices_without_instance = [
                    i for (i, instance) in enumerate(instances)
                    if instance is None]

                if len(indices_without_instance) > 0:
                    yield {'error': f'Couldn\'t get instances for indices: '
                                    f'{indices_without_instance}'}
                    return
                indices_to_compositions = {
                    i: AtomicComposition(m['execution_id'])
                    for (i, m) in enumerate(metadatas)
                }
                self.log.debug(
                    f'Idx to compositions {indices_to_compositions}')
                composition = IndicesComposition(
                    execution_id,
                    indices_to_compositions=indices_to_compositions,
                    tombstone_execution_ids=set())
            self.db_storage.store_execution_composition(composition)
        except Exception as e:
            self.log.exception('Exception running command.')
            yield {'error': str(e)}

    def _store_metadata_for_all_executions(
            self, command: [str], snapshot_id: str, parameters: dict,
            instance_market_spec: dict, execution_spec: dict,
            start_metadata: dict,
            parallel_indices_range: Optional[Tuple[int, int]],
            indices_per_execution: Optional[int],
            previous_execution_id: Optional[str],
            execution_id: str) -> [dict]:
        enriched_start_metadata = _enrich_start_metadata(
            execution_id, start_metadata, command, snapshot_id, parameters,
            instance_market_spec, execution_spec, parallel_indices_range,
            index_range_to_run=None,
            indices_per_execution=indices_per_execution,
            previous_execution_id=previous_execution_id)
        self.db_storage.store_start_metadata(
            execution_id, enriched_start_metadata)
        if parallel_indices_range is not None:
            if indices_per_execution is None:
                indices_per_execution = 1
            metadatas = []
            for i in range(parallel_indices_range[0],
                           parallel_indices_range[1],
                           indices_per_execution):
                enriched_start_metadata = _enrich_start_metadata(
                    _get_execution_uuid(),
                    start_metadata, command, snapshot_id, parameters,
                    instance_market_spec, execution_spec,
                    parallel_indices_range=None,
                    index_range_to_run=(i, i + indices_per_execution),
                    indices_per_execution=None,
                    previous_execution_id=previous_execution_id)
                metadatas.append(enriched_start_metadata)
                self.db_storage.store_start_metadata(
                    enriched_start_metadata['execution_id'],
                    enriched_start_metadata)
        else:
            metadatas = [enriched_start_metadata]
        return metadatas


def _get_execution_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))


def _enrich_start_metadata(
        execution_id: str,
        start_metadata: dict, command: [str], snapshot_id: str,
        parameters: dict, instance_market_spec: dict, execution_spec: dict,
        parallel_indices_range: Optional[Tuple[int, int]],
        index_range_to_run: Optional[Tuple[int, int]],
        indices_per_execution: Optional[int],
        previous_execution_id: Optional[str]) -> dict:
    enriched_start_metadata = deepcopy(start_metadata)
    enriched_start_metadata['execution_id'] = execution_id
    enriched_start_metadata['command'] = command
    enriched_start_metadata['snapshot_id'] = snapshot_id
    enriched_start_metadata['parameters'] = parameters
    enriched_start_metadata['instance_market_spec'] = instance_market_spec
    enriched_start_metadata['execution_spec'] = {
        k: v for k, v in execution_spec.items()
        if k not in {'user', 'project'}}
    enriched_start_metadata['execution_spec']['index_range_to_run'] = \
        index_range_to_run
    enriched_start_metadata['user'] = execution_spec['user']
    enriched_start_metadata['project'] = execution_spec['project']
    enriched_start_metadata['parallel_indices_range'] = parallel_indices_range
    enriched_start_metadata['indices_per_execution'] = indices_per_execution
    enriched_start_metadata['previous_execution_id'] = previous_execution_id
    return enriched_start_metadata


def _assign_instances(
        instances: [Optional[Instance]],
        parallel_indices_range: Optional[Tuple[int, int]],
        statuses_generators: [Iterator[dict]]) -> Iterator[dict]:
    # Whether was there a status update
    was_there_status = True
    while was_there_status:
        was_there_status = False
        for (i, statuses_generator) in enumerate(statuses_generators):
            status = next(statuses_generator)
            if status is None:
                continue
            was_there_status = True
            if 'message' in status:
                if parallel_indices_range is not None:
                    prefix = f'{i}: '
                else:
                    prefix = ''
                yield {'status': prefix + status['message']}
            if 'instance' in status:
                instances[i] = status['instance']
