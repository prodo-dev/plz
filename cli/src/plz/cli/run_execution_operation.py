import collections
import io
import itertools
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from glob import iglob
from typing import Iterator, Optional, Tuple

import docker.utils.build
import requests

from plz.cli import parameters
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.input_data import InputData
from plz.cli.log import log_error, log_info
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation, check_status, on_exception_reraise
from plz.cli.parameters import Parameters

ExecutionStatus = collections.namedtuple(
    'ExecutionStatus',
    ['running', 'success', 'code'])


class RunExecutionOperation(Operation):
    """Run an arbitrary command on a remote machine."""

    @staticmethod
    def prepare_argument_parser(parser, args):
        parser.add_argument('--command', type=str)
        cwd = os.getcwd()
        parser.add_argument('-o', '--output-dir',
                            type=str,
                            default=os.path.join(cwd, 'output'))
        parser.add_argument('-p', '--parameters', dest='parameters_file',
                            type=str)

    def __init__(self,
                 configuration: Configuration,
                 command: Optional[str],
                 output_dir: str,
                 parameters_file: str):
        super().__init__(configuration)
        self.configuration = configuration
        self.output_dir = output_dir
        self.parameters_file = parameters_file
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

        log_info('Capturing the context')
        build_context = self.capture_build_context()
        log_info('Building the program snapshot')
        snapshot_id = self.submit_context_for_building(build_context)
        if not snapshot_id:
            raise CLIException('We did not receive a snapshot ID.')

        if self.configuration.input:
            log_info('Capturing the input')
        with InputData.from_configuration(self.configuration) as input_data:
            input_id = input_data.publish()
            execution_spec = {
                'instance_type': self.configuration.instance_type,
                'user': self.configuration.user,
                'input_id': input_id,
            }
            execution_id, ok = self.post_execution_request(
                snapshot_id, params, execution_spec)

        if not execution_id:
            raise CLIException('We did not receive an execution ID.')
        log_info(f'Execution ID is: {execution_id}')

        skip_cleanup = False
        try:
            if not ok:
                raise CLIException('The command failed.')
            logs = LogsOperation(self.configuration, execution_id)
            logs.display_logs(execution_id)
        except CLIException as e:
            e.print(self.configuration)
            raise ExitWithStatusCodeException(e.exit_code)
        except KeyboardInterrupt:
            skip_cleanup = True
        finally:
            if not skip_cleanup:
                self.harvest(execution_id)

        status = self.get_status(execution_id)
        if status.running:
            raise CLIException(
                'Execution has not finished. This should not happen.'
                ' Please report it.')
        elif status.success:
            log_info('Execution succeeded.')
            self.retrieve_output_files(execution_id)
            log_info('Done and dusted.')
            return status.code
        else:
            raise CLIException(
                f'Execution failed with an exit status of {status.code}.',
                exit_code=status.code)

    def capture_build_context(self):
        context_dir = os.getcwd()
        dockerfile_path = os.path.join(context_dir, 'Dockerfile')
        dockerfile_created = False
        try:
            with open(dockerfile_path, mode='x') as dockerfile:
                dockerfile_created = True
                dockerfile.write(
                    f'FROM {self.configuration.image}\n'
                    f'WORKDIR /app\n'
                    f'COPY . ./\n'
                    f'CMD {self.configuration.command}\n'
                )
            os.chmod(dockerfile_path, 0o644)
            build_context = docker.utils.build.tar(
                path='.',
                exclude=_get_excluded_paths(self.configuration),
                gzip=True,
            )
        except FileExistsError as e:
            raise CLIException('The directory cannot have a Dockerfile.', e)
        finally:
            if dockerfile_created:
                os.remove(dockerfile_path)
        return build_context

    def submit_context_for_building(self, build_context):
        metadata = {
            'user': self.configuration.user,
            'project': self.configuration.project,
        }
        metadata_bytes = json.dumps(metadata).encode('utf-8')
        request_data = itertools.chain(
            io.BytesIO(metadata_bytes),
            io.BytesIO(b'\n'),
            build_context)
        response = requests.post(
            self.url('snapshots'),
            data=request_data,
            stream=True)
        check_status(response, requests.codes.ok)
        error = False
        snapshot_id: str = None
        for json_bytes in response.raw:
            data = json.loads(json_bytes.decode('utf-8'))
            if 'stream' in data:
                if not self.configuration.quiet_build:
                    print(data['stream'].rstrip())
            if 'error' in data:
                error = True
                log_error('The snapshot was not successfully created.')
                print(data['error'].rstrip())
            if 'id' in data:
                snapshot_id = data['id']
        if error:
            return None
        return snapshot_id

    def post_execution_request(
            self,
            snapshot_id: str,
            params: Parameters,
            execution_spec: dict) \
            -> Tuple[Optional[str], bool]:
        log_info('Sending request to start execution')

        response = requests.post(self.url('executions'), json={
            'command': self.command,
            'snapshot_id': snapshot_id,
            'parameters': params,
            'execution_spec': execution_spec
        }, stream=True)
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
        return execution_id, ok

    @on_exception_reraise('Retrieving the status failed.')
    def get_status(self, execution_id):
        response = requests.get(self.url('executions', execution_id, 'status'))
        check_status(response, requests.codes.ok)
        body = response.json()
        return ExecutionStatus(
            running=body['running'],
            success=body['success'],
            code=body['exit_status'])

    @on_exception_reraise('Retrieving the output failed.')
    def retrieve_output_files(self, execution_id: str):
        log_info('Retrieving the output...')
        response = requests.get(
            self.url('executions', execution_id, 'output', 'files'),
            stream=True)
        check_status(response, requests.codes.ok)
        try:
            os.makedirs(self.output_dir)
        except FileExistsError:
            raise CLIException(
                f'The output directory "{self.output_dir}" already exists.')
        for path in untar(response.raw, self.output_dir):
            print(path)

    def harvest(self, execution_id: str):
        log_info('Harvesting the output...')
        response = requests.delete(self.url('executions', execution_id))
        check_status(response, requests.codes.no_content)


def _is_git_present() -> bool:
    # noinspection PyBroadException
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            input=None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8')
        return result.returncode == 0 and result.stderr == '' and \
            len(result.stdout) > 0
    except Exception:
        return False


def _get_excluded_paths(configuration: Configuration):
    excluded_paths = [os.path.abspath(ep)
                      for p in configuration.excluded_paths
                      for ep in iglob(p, recursive=True)]
    included_paths = set(os.path.abspath(ip)
                         for p in configuration.included_paths
                         for ip in iglob(p, recursive=True))
    git_ignored_files = []

    # A value of None means "exclude if git is available"
    use_git = configuration.exclude_gitignored_files or (
        configuration.exclude_gitignored_files is None and _is_git_present())

    if use_git:
        git_ignored_files = _get_ignored_git_files()
    excluded_paths += git_ignored_files
    ep = [p[len(os.path.abspath('.')) + 1:]
          for p in excluded_paths if p not in included_paths]
    return ep


def _get_ignored_git_files() -> [str]:
    all_files = os.linesep.join(iglob('**', recursive=True))
    # Using --no-index, so that .gitignored but indexed files need to be
    # included explicitly. This is easy for development as, when testing, we
    # want to commit files and instruct the test to ignore them. If it's
    # annoying for users this can be changed in the future
    result = subprocess.run(
        ['git', 'check-ignore', '--stdin', '--no-index'],
        input=all_files,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    return_code = result.returncode
    # When there are no ignored files it returns with exit code 1
    correct_return_code = return_code == 0 or (
            return_code == 1 and result.stdout == '')
    if not correct_return_code or result.stderr != '':
        raise SystemError('Cannot list files from git.\n'
                          f'Return code is: {result.returncode}\n'
                          f'Stderr: [{result.stderr}]')
    return [os.path.abspath(p) for p in result.stdout.splitlines()]


def untar(stream: io.RawIOBase, output_dir: str) -> Iterator[str]:
    # The response is a tarball we need to extract into `output_dir`.
    with tempfile.TemporaryFile() as tarball:
        # `tarfile.open` needs to read from a real file, so we copy to one.
        shutil.copyfileobj(stream, tarball)
        # And rewind to the start.
        tarball.seek(0)
        tar = tarfile.open(fileobj=tarball)
        for tarinfo in tar.getmembers():
            # Drop the first segment, because it's just the name of the
            # directory that was tarred up, and we don't care.
            path_segments = tarinfo.name.split(os.sep)[1:]
            if path_segments:
                # Unfortunately we can't just pass `*path_segments`
                # because `os.path.join` explicitly expects an argument
                # for the first parameter.
                path = os.path.join(path_segments[0], *path_segments[1:])
                # Just because it's nice, yield the file to be extracted.
                yield path
                source: io.BufferedReader = tar.extractfile(tarinfo.name)
                if source:
                    # Finally, write the file.
                    absolute_path = os.path.join(output_dir, path)
                    os.makedirs(os.path.dirname(absolute_path),
                                exist_ok=True)
                    with open(absolute_path, 'wb') as dest:
                        shutil.copyfileobj(source, dest)
