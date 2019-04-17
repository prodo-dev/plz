import io
import itertools
import json
from typing import BinaryIO, Iterator, List, Optional, Tuple

import requests
from requests import Response

from plz.cli.exceptions import CLIException, RequestException
from plz.cli.server import Server
from plz.controller.api import Controller
from plz.controller.api.exceptions import ResponseHandledException
from plz.controller.api.types import InputMetadata, JSONString

_HTTP_RESPONSE_READ_CHUNK_SIZE = 1024 * 1024


class ControllerProxy(Controller):
    def __init__(self, server: Server):
        self.server = server

    @classmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    def ping(self, ping_timeout: int,
             build_timestamp: Optional[int] = None) -> dict:
        response = self.server.get('ping', timeout=ping_timeout)
        is_ok = response.status_code == requests.codes.ok
        if is_ok:
            return response.json()
        return {}

    def run_execution(self, snapshot_id: str, parameters: dict,
                      instance_market_spec: dict, execution_spec: dict,
                      start_metadata: dict,
                      parallel_indices_range: Optional[Tuple[int, int]],
                      indices_per_execution: Optional[int]) \
            -> Iterator[dict]:
        response = self.server.post(
            'executions',
            stream=True,
            json={
                'snapshot_id': snapshot_id,
                'parameters': parameters,
                'execution_spec': execution_spec,
                'instance_market_spec': instance_market_spec,
                'start_metadata': start_metadata,
                'parallel_indices_range': parallel_indices_range,
                'indices_per_execution': indices_per_execution
            })
        _check_status(response, requests.codes.accepted)
        return (json.loads(line) for line in response.iter_lines())

    def rerun_execution(self,
                        user: str,
                        project: str,
                        instance_max_uptime_in_minutes: Optional[int],
                        override_parameters: Optional[dict],
                        previous_execution_id: str,
                        instance_market_spec: dict) -> Iterator[dict]:
        response = self.server.post('executions/rerun',
                                    stream=True,
                                    json={
                                        'user':
                                            user,
                                        'project':
                                            project,
                                        'execution_id':
                                            previous_execution_id,
                                        'instance_market_spec':
                                            instance_market_spec,
                                        'override_parameters':
                                            override_parameters,
                                        'instance_max_uptime_in_minutes':
                                            instance_max_uptime_in_minutes
                                    })
        _check_status(response, requests.codes.accepted)
        return (json.loads(line) for line in response.iter_lines())

    def list_executions(self, user: str, list_for_all_users: bool) -> [dict]:
        response = self.server.get('executions',
                                   'list',
                                   params={
                                       'user': user,
                                       'list_for_all_users': list_for_all_users
                                   })
        _check_status(response, requests.codes.ok)
        return json.loads(response.content)['executions']

    def get_status(self, execution_id: str) -> dict:
        response = self.server.get('executions', execution_id, 'status')
        _check_status(response, requests.codes.ok)
        return response.json()

    def get_logs(self, execution_id: str, since: Optional[int]) \
            -> Iterator[bytes]:
        response = self.server.get(
            'executions',
            execution_id,
            'logs',
            params={'since': since} if since is not None else {},
            stream=True)
        _check_status(response, requests.codes.ok)
        # Do not read in chunks as otherwise the logs don't flow interactively
        return response.raw

    def get_output_files(self,
                         execution_id: str,
                         path: Optional[str],
                         index: Optional[int]) -> Iterator[bytes]:
        response = self.server.get(
            'executions',
            execution_id,
            'output',
            'files',
            codes_with_exceptions={requests.codes.not_implemented},
            params={
                'path': path, 'index': index
            },
            stream=True)
        _check_status(response, requests.codes.ok)
        # Read in chunks as to avoid several writes for long files
        return _read_response_in_chunks(response)

    def get_measures(
            self, execution_id: str, summary: bool, index: Optional[int]) \
            -> Iterator[JSONString]:
        response = self.server.get(
            'executions',
            execution_id,
            'measures',
            params={
                'summary': summary, 'index': index
            },
            stream=True,
            codes_with_exceptions={requests.codes.conflict})
        _check_status(response, requests.codes.ok)
        return (line.decode('utf-8') for line in response.raw)

    def delete_execution(self,
                         execution_id: str,
                         fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        response = self.server.delete('executions',
                                      execution_id,
                                      params={
                                          'fail_if_deleted': fail_if_deleted,
                                          'fail_if_running': fail_if_running,
                                      },
                                      codes_with_exceptions={
                                          requests.codes.expectation_failed,
                                          requests.codes.conflict
                                      })
        _check_status(response, requests.codes.no_content)

    def get_history(self, user: str, project: str) -> Iterator[JSONString]:
        response = self.server.get('executions',
                                   user,
                                   project,
                                   'history',
                                   stream=True)
        _check_status(response, requests.codes.ok)
        return (line.decode('utf-8') for line in response.raw)

    def create_snapshot(self, image_metadata: dict, context: BinaryIO) -> \
            Iterator[JSONString]:
        metadata_bytes = json.dumps(image_metadata).encode('utf-8')
        request_data = itertools.chain(io.BytesIO(metadata_bytes),
                                       io.BytesIO(b'\n'),
                                       context)
        response = self.server.post('snapshots',
                                    data=request_data,
                                    stream=True)
        _check_status(response, requests.codes.ok)
        return (frag.decode('utf-8') for frag in response.raw)

    def put_input(self,
                  input_id: str,
                  input_metadata: InputMetadata,
                  input_data_stream: BinaryIO) -> None:
        response = self.server.put(
            'data',
            'input',
            input_id,
            data=input_data_stream,
            stream=True,
            params={
                'user': input_metadata.user,
                'project': input_metadata.project,
                'path': input_metadata.path,
                'timestamp_millis': input_metadata.timestamp_millis
            })
        _check_status(response, requests.codes.ok)
        if input_id != response.json()['id']:
            raise CLIException('Got wrong input id back from the server')

    def check_input_data(self, input_id: str, metadata: InputMetadata) -> bool:
        response = self.server.head(
            'data',
            'input',
            input_id,
            codes_with_exceptions={requests.codes.bad_request},
            params={
                'user': metadata.user,
                'project': metadata.project,
                'path': metadata.path,
                'timestamp_millis': metadata.timestamp_millis
            })
        if response.status_code == requests.codes.ok:
            return True
        elif response.status_code == requests.codes.not_found:
            return False
        else:
            raise RequestException(response)

    def get_input_id_or_none(self, metadata: InputMetadata) -> Optional[str]:
        response = self.server.get(
            'data',
            'input',
            'id',
            params={
                'user': metadata.user,
                'project': metadata.project,
                'path': metadata.path,
                'timestamp_millis': metadata.timestamp_millis
            })
        _check_status(response, requests.codes.ok)
        return response.json()['id']

    def delete_input_data(self, input_id: str):
        response = self.server.delete('data', 'input', input_id)
        _check_status(response, requests.codes.ok)

    def get_user_last_execution_id(self, user: str) -> Optional[str]:
        response = self.server.get('users', user, 'last_execution_id')
        _check_status(response, requests.codes.ok)
        response_object = json.loads(response.content)
        # TODO: Make it consistent with the input data methods, and return None
        if 'execution_id' in response_object:
            return response_object['execution_id']
        else:
            # TODO: when used with `plz last` the error should be different
            # This bad behaviour is prior to plz serverless
            raise ValueError('Expected an execution ID')

    def kill_instances(self,
                       user: str,
                       instance_ids: Optional[List[str]],
                       ignore_ownership: bool,
                       including_idle: Optional[bool],
                       force_if_not_idle: bool) -> bool:
        response = self.server.post(
            'instances',
            'kill',
            json={
                'all_of_them_plz': instance_ids is None,
                'ignore_ownership': ignore_ownership,
                'including_idle': including_idle,
                'instance_ids': instance_ids,
                'force_if_not_idle': force_if_not_idle,
                'user': user
            },
            codes_with_exceptions={requests.codes.conflict})
        _check_status(response, requests.codes.ok)
        response_json = response.json()
        return response_json['were_there_instances_to_kill']

    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        response = self.server.get('executions',
                                   'describe',
                                   execution_id,
                                   stream=True)
        _check_status(response, requests.codes.ok)
        return response.json()

    def get_execution_composition(self, execution_id: str) -> dict:
        response = self.server.get('executions', 'composition', execution_id)
        _check_status(response, requests.codes.ok)
        return response.json()

    def harvest(self) -> None:
        response = self.server.post('executions', 'harvest')
        _check_status(response, requests.codes.no_content)


def _check_status(response: requests.Response, expected_status: int):
    if response.status_code != expected_status:
        raise RequestException(response)


def _read_response_in_chunks(http_response: Response) \
        -> Iterator[bytes]:
    while True:
        bs = http_response.raw.read(_HTTP_RESPONSE_READ_CHUNK_SIZE)
        if bs is None or len(bs) == 0:
            return
        yield bs
