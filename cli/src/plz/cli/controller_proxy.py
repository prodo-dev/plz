import io
import itertools
import json
from typing import BinaryIO, Iterator, Optional

import requests

from plz.cli.exceptions import CLIException, RequestException
from plz.cli.log import log_error
from plz.cli.operation import check_status
from plz.cli.server import Server
from plz.controller import Controller
from plz.controller.controller import JSONString
from plz.controller.exceptions import ResponseHandledException
from plz.controller.types import InputMetadata


class ControllerProxy(Controller):
    def __init__(self, server: Server, ping_timeout: int):
        self.server = server
        self.ping_timeout = ping_timeout

    @classmethod
    def handle_exception(cls, exception: ResponseHandledException):
        pass

    def ping(self) -> dict:
        response = self.server.get('ping', timeout=self.ping_timeout)
        is_ok = response.status_code == requests.codes.ok
        if is_ok:
            return json.loads(response.content)
        return {}

    def run_execution(self, command: [str], snapshot_id: str, parameters: dict,
                      instance_market_spec: dict, execution_spec: dict,
                      start_metadata: dict) -> Iterator[dict]:
        response = self.server.post(
            'executions',
            stream=True,
            json={
                'command': command,
                'snapshot_id': snapshot_id,
                'parameters': parameters,
                'execution_spec': execution_spec,
                'instance_market_spec': instance_market_spec,
                'start_metadata': start_metadata
            })
        check_status(response, requests.codes.accepted)
        return (json.loads(line) for line in response.iter_lines())

    def rerun_execution(
            self, user: str, project: str, previous_execution_id: str,
            instance_market_spec: dict) -> Iterator[dict]:
        response = self.server.post(
            'executions/rerun', stream=True,
            json={'user': user,
                  'project': project,
                  'execution_id': previous_execution_id,
                  'instance_market_spec': instance_market_spec})
        check_status(response, requests.codes.accepted)
        return (json.loads(line) for line in response.iter_lines())

    def list_executions(self) -> [dict]:
        response = self.server.get('executions', 'list')
        check_status(response, requests.codes.ok)
        return json.loads(response.content)['executions']

    def get_status(self, execution_id: str) -> dict:
        response = self.server.get(
            'executions', execution_id, 'status')
        check_status(response, requests.codes.ok)
        return response.json()

    def get_logs(self, execution_id: str, since: Optional[int]) \
            -> Iterator[bytes]:
        response = self.server.get(
            'executions', execution_id, 'logs',
            params={'since': since} if since is not None else {},
            stream=True)
        check_status(response, requests.codes.ok)
        return response.raw

    def get_output_files(self, execution_id: str) -> Iterator[bytes]:
        response = self.server.get(
            'executions', execution_id, 'output', 'files',
            stream=True)
        check_status(response, requests.codes.ok)
        return response.raw

    def get_measures(
            self, execution_id: str, summary: bool) -> Iterator[JSONString]:
        response = self.server.get(
            'executions', execution_id, 'measures',
            params={'summary': summary},
            stream=True,
            codes_with_exceptions={requests.codes.conflict})
        check_status(response, requests.codes.ok)
        return (line.decode('utf-8') for line in response.raw)

    def delete_execution(self, execution_id: str, fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        response = self.server.delete(
            'executions', execution_id,
            params={
                'fail_if_deleted': fail_if_deleted,
                'fail_if_running': fail_if_running,
            },
            codes_with_exceptions={
                requests.codes.expectation_failed, requests.codes.conflict})
        check_status(response, requests.codes.no_content)

    def get_history(self, user: str, project: str) -> Iterator[JSONString]:
        response = self.server.get(
            'executions', user, project, 'history', stream=True)
        check_status(response, requests.codes.ok)
        return (line.decode('utf-8') for line in response.raw)

    def create_snapshot(self, image_metadata: dict, context: BinaryIO) -> \
            Iterator[JSONString]:
        metadata_bytes = json.dumps(image_metadata).encode('utf-8')
        request_data = itertools.chain(
            io.BytesIO(metadata_bytes),
            io.BytesIO(b'\n'),
            context)
        response = self.server.post(
            'snapshots',
            data=request_data,
            stream=True)
        check_status(response, requests.codes.ok)
        return (frag.decode('utf-8') for frag in response.raw)

    def put_input(self, input_id: str, input_metadata: InputMetadata,
                  input_data_stream: BinaryIO) -> None:
        response = self.server.put(
            'data', 'input', input_id,
            data=input_data_stream,
            stream=True,
            params={'user': input_metadata.user,
                    'project': input_metadata.project,
                    'path': input_metadata.path,
                    'timestamp_millis': input_metadata.timestamp_millis})
        check_status(response, requests.codes.ok)
        if input_id != response.json()['id']:
            raise CLIException('Got wrong input id back from the server')

    def check_input_data(self, input_id: str,
                         metadata: InputMetadata) -> bool:
        response = self.server.head(
            'data', 'input', input_id,
            codes_with_exception={requests.codes.bad_request},
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
            'data', 'input', 'id',
            params={'user': metadata.user,
                    'project': metadata.project,
                    'path': metadata.path,
                    'timestamp_millis': metadata.timestamp_millis})
        check_status(response, requests.codes.ok)
        return response.json()['id']

    def delete_input_data(self, input_id: str):
        response = self.server.delete('data', 'input', input_id)
        check_status(response, requests.codes.ok)

    def get_user_last_execution_id(self, user: str) -> Optional[str]:
        response = self.server.get(
            'users', user, 'last_execution_id')
        check_status(response, requests.codes.ok)
        response_object = json.loads(response.content)
        # Make it consistent with the input data methods, and return None
        if 'execution_id' in response_object:
            return response_object['execution_id']
        else:
            # TODO: when used with `plz last` the error should be different
            # This bad behaviour is prior to plz serverless
            raise ValueError('Expected an execution ID')

    def kill_instances(
            self, instance_ids: Optional[str], force_if_not_idle: bool) \
            -> bool:
        response = self.server.post('instances', 'kill', json={
            'all_of_them_plz': instance_ids is None,
            'instance_ids': instance_ids if instance_ids is not None else [],
            'force_if_not_idle': force_if_not_idle
        })

        response_json = response.json()
        if response.status_code != requests.codes.ok:
            if 'failed_instance_ids_to_messages' in response_json:
                fails = response_json['failed_instance_ids_to_messages']
                log_error(
                    'Error terminating instances: \n' + ''.join(
                        [f'{instance_id}: {message}\n'
                         for instance_id, message in fails.items()]))
            raise CLIException(
                'Couldn\'t terminate all instances. You can use '
                '--force-if-not-idle for non-idle instances')
        # TODO: The warning message was the mechanism before serverless
        return response_json.get('were_there_instances_to_kill', True) and \
            'warning_message' not in response_json

    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        response = self.server.get(
            'executions', 'describe', execution_id, stream=True)
        check_status(response, requests.codes.ok)
        return response.json()
