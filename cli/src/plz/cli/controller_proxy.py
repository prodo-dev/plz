import json
from typing import Optional, Iterator, BinaryIO, Union

import requests

from plz.cli.exceptions import CLIException
from plz.cli.operation import check_status
from plz.cli.server import Server
from plz.controller import Controller
from plz.controller.controller import JSONString
from plz.controller.exceptions import ResponseHandledException
from plz.controller.input_data import InputMetadata
from plz.controller.instances.instance_base import \
    InstanceStillRunningException


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
                      start_metadata: dict,
                      previous_execution_id: Optional[str] = None) \
            -> Iterator[dict]:
        response = self.server.post(
            'executions',
            stream=True,
            json={
                'command': command,
                'snapshot_id': snapshot_id,
                'parameters': parameters,
                'execution_spec': execution_spec,
                'instance_market_spec': instance_market_spec,
                'start_metadata': start_metadata,
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
            stream=True)
        if response.status_code == requests.codes.conflict:
            raise CLIException(
                'Process is still running, run `plz stop` if you want to '
                'terminate it')
        check_status(response, requests.codes.ok)
        return (line for line in response.raw)

    def delete_execution(self, execution_id: str, fail_if_running: bool,
                         fail_if_deleted: bool) -> None:
        response = self.server.delete(
            'executions', execution_id,
            params={
                'fail_if_deleted': True,
            })
        if response.status_code == requests.codes.expectation_failed:
            # TODO: move this exception to the controller module
            raise InstanceStillRunningException(execution_id)
        check_status(response, requests.codes.no_content)

    def get_history(self, user: str, project: str) -> JSONString:
        pass

    def create_snapshot(self, metadata_str: str, context: BinaryIO) -> \
            Iterator[Union[bytes, str]]:
        pass

    def put_input(self, input_id: str, input_data_stream: BinaryIO) -> None:
        pass

    def check_input_data(self, expected_input_id: str,
                         metadata: InputMetadata) -> bool:
        pass

    def get_input_id_or_none(self, metadata: InputMetadata) -> Optional[str]:
        pass

    def delete_input_data(self, input_id: str):
        pass

    def get_user_last_execution_id(self, user: str) -> str:
        pass

    def kill_instances(self, instance_ids: [str],
                       force_if_not_idle: bool) -> dict:
        pass

    def describe_execution_entrypoint(self, execution_id: str) -> dict:
        pass
