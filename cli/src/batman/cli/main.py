import argparse
import io
import itertools
import json
import os
import os.path
import shutil
import sys
import tarfile
import tempfile
from typing import Optional, Tuple

import docker.utils.build
import requests

from batman.cli import parameters
from batman.cli.configuration import Configuration, ValidationException
from batman.cli.exceptions import CLIException
from batman.cli.log import log_error, log_info
from batman.cli.parameters import Parameters


def on_exception_reraise(message):
    def wrapper(f):
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as cause:
                raise CLIException(message, cause)

        return wrapped

    return wrapper


class RunCommand:
    """Run an arbitrary command on a remote machine."""

    @staticmethod
    def prepare_argument_parser(parser):
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
        self.configuration = configuration
        self.output_dir = output_dir
        self.parameters_file = parameters_file
        self.prefix = f'http://{configuration.host}:{configuration.port}'
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

        if snapshot_id:
            execution_spec = {
                'instance_type': self.configuration.instance_type,
            }
            execution_id, ok = self.issue_command(
                snapshot_id, params, execution_spec)
            if execution_id:
                if ok:
                    self.display_logs(execution_id)
                    self.retrieve_output_files(execution_id)
                self.cleanup(execution_id)
            log_info('Done and dusted.')

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
                exclude=self.configuration.excluded_paths,
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
            [metadata_bytes, b'\n'],
            build_context)
        response = requests.post(
            self.url('snapshots'), request_data, stream=True)
        check_status(response, requests.codes.ok)
        error = False
        snapshot_id: str = None
        for json_bytes in response.raw:
            data = json.loads(json_bytes.decode('utf-8'))
            if 'stream' in data:
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

    def issue_command(
            self, snapshot_id: str, params: Parameters, execution_spec: dict) \
            -> Tuple[Optional[str], bool]:
        log_info('Issuing the command on a new box')

        response = requests.post(self.url('commands'), json={
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

    @on_exception_reraise("Displaying the logs failed.")
    def display_logs(self, execution_id: str):
        log_info('Streaming logs...')
        response = requests.get(self.url('commands', execution_id, 'logs'),
                                stream=True)
        check_status(response, requests.codes.ok)
        for line in response.raw:
            print(line.decode('utf-8'), end='')
        print()

    @on_exception_reraise("Retrieving the output failed.")
    def retrieve_output_files(self, execution_id: str):
        log_info('Retrieving the output...')
        response = requests.get(
            self.url('commands', execution_id, 'output', 'files'),
            stream=True)
        try:
            check_status(response, requests.codes.ok)
        except FileExistsError:
            raise CLIException(
                f'The output directory "{self.output_dir}" already exists.')
        os.makedirs(self.output_dir)
        # The response is a tarball we need to extract into `self.output_dir`.
        with tempfile.TemporaryFile() as tarball:
            # `tarfile.open` needs to read from a real file, so we copy to one.
            shutil.copyfileobj(response.raw, tarball)
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
                    # Just because it's nice, print the file to be extracted.
                    print(path)
                    source: io.BufferedReader = tar.extractfile(tarinfo.name)
                    if source:
                        # Finally, write the file.
                        absolute_path = os.path.join(self.output_dir, path)
                        os.makedirs(os.path.dirname(absolute_path),
                                    exist_ok=True)
                        with open(absolute_path, 'wb') as dest:
                            shutil.copyfileobj(source, dest)

    def cleanup(self, execution_id: str):
        log_info('Cleaning up all detritus...')
        response = requests.delete(self.url('commands', execution_id))
        check_status(response, requests.codes.no_content)

    def url(self, *path_segments):
        return self.prefix + '/' + '/'.join(path_segments)


class RequestException(Exception):
    def __init__(self, response: requests.Response):
        try:
            body = response.json()
        except ValueError:
            body = response.text
        super().__init__(
            f'Request failed with status code {response.status_code}.\n' +
            f'Response:\n{body}'
        )


COMMANDS = {
    'run': RunCommand,
}


def check_status(response, expected_status):
    if response.status_code != expected_status:
        raise RequestException(response)


def main(args):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='commands', dest='command_name')
    for name, command in COMMANDS.items():
        subparser = subparsers.add_parser(name, help=command.__doc__)
        command.prepare_argument_parser(subparser)
    options = parser.parse_args(args)

    try:
        configuration = Configuration.load()
    except ValidationException as e:
        e.print()
        sys.exit(2)

    command_name = options.command_name
    option_dict = options.__dict__
    del option_dict['command_name']

    command = COMMANDS[command_name](configuration, **option_dict)
    try:
        command.run()
    except CLIException as e:
        e.print(configuration)
        sys.exit(1)


main(sys.argv[1:])
