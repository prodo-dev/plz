import io
import itertools
import json
import os
import time
from typing import Any, Callable, Optional, Tuple

import requests

from plz.cli import parameters
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.git import get_head_commit_or_none
from plz.cli.input_data import InputData
from plz.cli.log import log_debug, log_error, log_info
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation, add_output_dir_arg, check_status
from plz.cli.parameters import Parameters
from plz.cli.retrieve_measures_operation import RetrieveMeasuresOperation
from plz.cli.retrieve_output_operation import RetrieveOutputOperation
from plz.cli.show_status_operation import ShowStatusOperation
from plz.cli.snapshot import capture_build_context


class RunExecutionOperation(Operation):
    """Run an arbitrary command on a remote machine."""

    @classmethod
    def name(cls):
        return 'run'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument('--command', type=str)
        add_output_dir_arg(parser)
        parser.add_argument('-p', '--parameters', dest='parameters_file',
                            type=str)

    def __init__(self,
                 configuration: Configuration,
                 command: Optional[str],
                 output_dir: str,
                 parameters_file: str,
                 list_excluded_paths: bool,
                 list_snapshot_files: bool):
        super().__init__(configuration)
        self.configuration = configuration
        self.output_dir = output_dir
        self.parameters_file = parameters_file
        self.list_excluded_paths = list_excluded_paths
        self.list_snapshot_files = list_snapshot_files
        if command:
            self.command = ['sh', '-c', command, '-s']
        else:
            self.command = configuration.command

    def run(self):
        if not self.command:
            raise CLIException('No command specified!')

        if os.path.exists(self.output_dir):
            raise CLIException(
                f'The output directory "{self.output_dir}" already exists.')

        params = parameters.parse_file(self.parameters_file)

        exclude_gitignored_files = \
            self.configuration.exclude_gitignored_files
        snapshot_path = '.'

        def build_context_suboperation():
            return capture_build_context(
                image=self.configuration.image,
                image_extensions=self.configuration.image_extensions,
                command=self.configuration.command,
                snapshot_path=snapshot_path,
                excluded_paths=self.configuration.excluded_paths,
                included_paths=self.configuration.included_paths,
                exclude_gitignored_files=exclude_gitignored_files,
            )

        with self.suboperation(
                'Capturing the context',
                build_context_suboperation) as build_context:
            snapshot_id = self.suboperation(
                    'Building the program snapshot',
                    lambda: self.submit_context_for_building(build_context))
        input_id = self.suboperation(
                'Capturing the input',
                self.capture_input,
                if_set=self.configuration.input)
        execution_id, ok = self.suboperation(
                'Sending request to start execution',
                lambda: self.start_execution(snapshot_id, params, input_id,
                                             snapshot_path))
        self.execution_id = execution_id
        log_info(f'Execution ID is: {execution_id}')

        retrieve_output_operation = RetrieveOutputOperation(
            self.configuration,
            output_dir=self.output_dir,
            execution_id=execution_id)

        cancelled = False
        try:
            if not ok:
                raise CLIException('The command failed.')
            logs = LogsOperation(self.configuration,
                                 execution_id=execution_id,
                                 since='start')
            logs.display_logs(execution_id, print_interrupt_message=True)
        except CLIException as e:
            e.print(self.configuration)
            raise ExitWithStatusCodeException(e.exit_code)
        except KeyboardInterrupt:
            cancelled = True
        finally:
            if not cancelled:
                self.suboperation(
                        'Harvesting the output...',
                        retrieve_output_operation.harvest)

        if cancelled:
            return

        retrieve_measures_operation = RetrieveMeasuresOperation(
            self.configuration, execution_id=self.get_execution_id(),
            summary=True)
        self.suboperation(
            'Retrieving summary of measures (if present)...',
            retrieve_measures_operation.retrieve_measures)

        show_status_operation = ShowStatusOperation(
            self.configuration, execution_id=execution_id)
        status = show_status_operation.get_status()
        if status.running:
            raise CLIException(
                'Execution has not finished. This should not happen.'
                ' Please report it.')
        elif status.success:
            log_info('Execution succeeded.')
            self.suboperation(
                    'Retrieving the output...',
                    retrieve_output_operation.retrieve_output)
            log_info('Done and dusted.')
            return status.code
        else:
            raise CLIException(
                f'Execution failed with an exit status of {status.code}.',
                exit_code=status.code)

    def submit_context_for_building(self, build_context: io.FileIO) -> str:
        metadata = {
            'user': self.configuration.user,
            'project': self.configuration.project,
        }
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        request_data = itertools.chain(
            io.BytesIO(metadata_bytes),
            io.BytesIO(b'\n'),
            build_context)
        response = self.server.post(
            'snapshots',
            data=request_data,
            stream=True)
        check_status(response, requests.codes.ok)
        errors = []
        snapshot_id: str = None
        for json_bytes in response.raw:
            data = json.loads(json_bytes.decode('utf-8'))
            if 'stream' in data:
                if not self.configuration.quiet_build:
                    print(data['stream'].rstrip())
            if 'error' in data:
                errors.append(data['error'].rstrip())
            if 'id' in data:
                snapshot_id = data['id']
        if errors or not snapshot_id:
            log_error('The snapshot was not successfully created.')
            for error in errors:
                print(error)
            raise CLIException('We did not receive a snapshot ID.')
        return snapshot_id

    def capture_input(self) -> Optional[str]:
        with InputData.from_configuration(self.configuration) as input_data:
            return input_data.publish()

    def start_execution(
            self,
            snapshot_id: str,
            params: Parameters,
            input_id: Optional[str],
            snapshot_path: str) \
            -> Tuple[Optional[str], bool]:
        configuration = self.configuration
        execution_spec = {
            'instance_type': configuration.instance_type,
            'user': configuration.user,
            'input_id': input_id,
            'docker_run_args': configuration.docker_run_args
        }
        commit = get_head_commit_or_none(snapshot_path)
        response = self.server.post(
            'executions',
            stream=True,
            json={
                'command': self.command,
                'snapshot_id': snapshot_id,
                'parameters': params,
                'execution_spec': execution_spec,
                'start_metadata': {
                    'commit': commit,
                    'configuration': configuration.as_dict()
                },
            })
        check_status(response, requests.codes.accepted)
        execution_id: Optional[str] = None
        ok = True
        for line in response.iter_lines():
            data = json.loads(line)
            if 'id' in data:
                execution_id = data['id']
            elif 'status' in data:
                print('Instance status:', data['status'].rstrip())
            elif 'error' in data:
                ok = False
                log_error(data['error'].rstrip())
        if not execution_id:
            raise CLIException('We did not receive an execution ID.')
        return execution_id, ok

    def suboperation(self,
                     name: str,
                     f: Callable[..., Any],
                     if_set: bool = True):
        if not if_set:
            return
        log_info(name)
        start_time = time.time()
        result = f()
        end_time = time.time()
        time_taken = end_time - start_time
        if self.configuration.debug:
            log_debug('Time taken: %.2fs' % time_taken)
        return result
