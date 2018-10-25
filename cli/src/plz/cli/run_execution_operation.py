import json
import os
from typing import Any, BinaryIO, Callable, Iterator, Optional, Tuple

import time

from plz.cli import parameters
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.git import get_head_commit_or_none
from plz.cli.input_data import InputData
from plz.cli.log import log_debug, log_error, log_info, log_warning
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation, add_output_dir_arg
from plz.cli.parameters import Parameters
from plz.cli.retrieve_measures_operation import RetrieveMeasuresOperation
from plz.cli.retrieve_output_operation import RetrieveOutputOperation
from plz.cli.show_status_operation import ShowStatusOperation
from plz.cli.snapshot import capture_build_context


class RunExecutionOperation(Operation):
    """Run an arbitrary command on a remote machine"""

    @classmethod
    def name(cls):
        return 'run'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument('--command', type=str, help='Command to run')
        add_output_dir_arg(parser)
        parser.add_argument('-p', '--parameters', dest='parameters_file',
                            help='Json file where parameters are stored',
                            type=str)
        parser.add_argument('--detach', '-d', action='store_true',
                            default=False,
                            help='Make CLI exit as soon as the job is \n'
                                 'running (does not print logs, or download \n'
                                 'outputs, etc.)')

    def __init__(self,
                 configuration: Configuration,
                 command: Optional[str],
                 output_dir: str,
                 parameters_file: Optional[str],
                 detach: bool):
        super().__init__(configuration)
        self.configuration = configuration
        self.output_dir = output_dir
        self.parameters_file = parameters_file
        self.detach = detach
        if command:
            self.command = ['sh', '-c', command, '-s']
        else:
            self.command = configuration.command

    def run(self):
        if not self.command:
            raise CLIException('No command specified! Use --command or '
                               'include a `command` entry in plz.config.json')

        if not self.configuration.image:
            raise CLIException('No image specified! Include an `image` entry '
                               'in plz.config.json')

        if os.path.exists(self.output_dir):
            raise CLIException(
                f'The output directory "{self.output_dir}" already exists.')

        params = parameters.parse_file(self.parameters_file)

        exclude_gitignored_files = \
            self.configuration.exclude_gitignored_files
        context_path = self.configuration.context_path

        def build_context_suboperation():
            return capture_build_context(
                image=self.configuration.image,
                image_extensions=self.configuration.image_extensions,
                command=self.configuration.command,
                context_path=context_path,
                excluded_paths=self.configuration.excluded_paths,
                included_paths=self.configuration.included_paths,
                exclude_gitignored_files=exclude_gitignored_files,
            )

        retries = self.configuration.workarounds['docker_build_retries']
        while retries + 1 > 0:
            with self.suboperation(
                    f'Capturing the files in {os.path.abspath(context_path)}',
                    build_context_suboperation) as build_context:
                try:
                    snapshot_id = self.suboperation(
                        'Building the program snapshot',
                        lambda: self.submit_context_for_building(
                            build_context))
                    break
                except CLIException as e:
                    if type(e.__cause__) == PullAccessDeniedException \
                            and retries > 0:
                        log_warning(str(e))
                        log_warning(
                            'This might be a transient error. Retrying')
                        retries -= 1
                        time.sleep(7)
                    else:
                        raise e

        input_id = self.suboperation(
                'Capturing the input',
                self.capture_input,
                if_set=self.configuration.input)
        execution_id, was_start_ok = self.suboperation(
                'Sending request to start execution',
                lambda: self.start_execution(snapshot_id, params, input_id,
                                             context_path))
        self.execution_id = execution_id
        self.follow_execution(was_start_ok)

    def follow_execution(self, was_start_ok: bool):
        log_info(f'Execution ID is: {self.execution_id}')

        if self.detach:
            return
        retrieve_output_operation = RetrieveOutputOperation(
            self.configuration,
            output_dir=self.output_dir,
            execution_id=self.execution_id,
            force_if_running=False,
            path=None)

        cancelled = False
        try:
            if not was_start_ok:
                raise CLIException('The command failed.')
            logs = LogsOperation(self.configuration,
                                 execution_id=self.execution_id,
                                 since='start')
            logs.display_logs(self.execution_id, print_interrupt_message=True)
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
            self.configuration, execution_id=self.execution_id, summary=True)
        self.suboperation(
            'Retrieving summary of measures (if present)...',
            retrieve_measures_operation.retrieve_measures)

        show_status_operation = ShowStatusOperation(
            self.configuration, execution_id=self.execution_id)
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

    def submit_context_for_building(self, build_context: BinaryIO) -> str:
        metadata = {
            'user': self.configuration.user,
            'project': self.configuration.project,
        }
        status_json_strings = self.controller.create_snapshot(
            metadata, build_context)
        errors = []
        snapshot_id: str = None
        for json_str in status_json_strings:
            data = json.loads(json_str)
            if 'stream' in data:
                if not self.configuration.quiet_build:
                    print(data['stream'], end='', flush=True)
            if 'error' in data:
                errors.append(data['error'].rstrip())
            if 'id' in data:
                snapshot_id = data['id']
        if errors or not snapshot_id:
            log_error('The snapshot was not successfully created.')
            pull_access_denied = False
            for error in errors:
                if error.startswith('pull access denied'):
                    pull_access_denied = True
                print(error)
            exc_message = 'We did not receive a snapshot ID.'
            if pull_access_denied:
                raise CLIException(exc_message) \
                    from PullAccessDeniedException()
            else:
                raise CLIException(exc_message)
        return snapshot_id

    def capture_input(self) -> Optional[str]:
        with InputData.from_configuration(
                self.configuration, self.controller) as input_data:
            return input_data.publish()

    def start_execution(
            self,
            snapshot_id: str,
            params: Parameters,
            input_id: Optional[str],
            context_path: str) \
            -> Tuple[Optional[str], bool]:
        configuration = self.configuration
        execution_spec = {
            'instance_type': configuration.instance_type,
            'user': configuration.user,
            'project': configuration.project,
            'input_id': input_id,
            'docker_run_args': configuration.docker_run_args,
            'instance_max_uptime_in_minutes':
                configuration.instance_max_uptime_in_minutes,
        }
        instance_market_spec = self.get_instance_market_spec()
        commit = get_head_commit_or_none(context_path)
        response_dicts = self.controller.run_execution(
            command=self.command,
            snapshot_id=snapshot_id,
            parameters=params,
            execution_spec=execution_spec,
            instance_market_spec=instance_market_spec,
            start_metadata={
                'commit': commit,
                'configuration': {
                    k: v for k, v in configuration.as_dict().items()
                    # User and project are present in the execution spec
                    if k not in {'user', 'project'}
                }
            }
        )
        return RunExecutionOperation.get_execution_id_from_start_response(
            response_dicts)

    @staticmethod
    def get_execution_id_from_start_response(
            response_dicts: Iterator[dict]) -> Tuple[str, bool]:
        execution_id: Optional[str] = None
        ok = True
        for data in response_dicts:
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

    def get_instance_market_spec(self) -> dict:
        return {
            k: getattr(self.configuration, k)
            for k in ('instance_market_type',
                      'instance_max_idle_time_in_minutes',
                      'max_bid_price_in_dollars_per_hour')
        }

    def get_execution_id(self):
        # Override this method, in this operation we shouldn't call the server
        # asking for the previous one
        return self.execution_id

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


class PullAccessDeniedException(Exception):
    pass
