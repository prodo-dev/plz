import argparse
import itertools
import json
import os
import os.path
import sys
import traceback
from typing import Optional, Tuple

import docker.utils.build
import requests

from configuration import Configuration, ValidationException


class RunCommand:
    """Run an arbitrary command on a remote machine."""

    @staticmethod
    def prepare_argument_parser(parser):
        parser.add_argument('--command', type=str)

    def __init__(self, configuration: Configuration, command: Optional[str]):
        self.configuration = configuration
        self.prefix = f'http://{configuration.host}:{configuration.port}'
        self.command = \
            ['sh', '-c', command] if command else self.configuration.command

    def run(self) -> bool:
        if not self.command:
            log_error('No command specified!')
            return False

        log_info('Capturing the context')
        build_context = self.capture_build_context()
        log_info('Building the program snapshot')
        snapshot_id = self.submit_context_for_building(build_context)

        if snapshot_id:
            execution_id, ok = self.issue_command(snapshot_id)
            try:
                if ok and execution_id:
                    self.display_logs(execution_id)
            except RequestException:
                log_error('Displaying the logs failed.')
                traceback.print_exc()
                return False
            if execution_id:
                self.cleanup(execution_id)
            log_info('Done and dusted.')
            return True

    def capture_build_context(self):
        context_dir = os.getcwd()
        dockerfile_path = os.path.join(context_dir, 'Dockerfile')
        dockerfile_created = False
        try:
            with open(dockerfile_path, mode='x') as dockerfile:
                dockerfile_created = True
                dockerfile.write(''.join(line + '\n' for line in [
                    f'FROM {self.configuration.image}',
                    f'WORKDIR /app',
                    f'COPY . ./',
                    f'CMD {self.configuration.command}'
                ]))
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

    def issue_command(self, snapshot_id: str) -> Tuple[Optional[str], bool]:
        log_info('Issuing the command on a new box')
        response = requests.post(self.url('commands'), json={
            'command': self.command,
            'snapshot_id': snapshot_id,
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

    def display_logs(self, execution_id: str):
        log_info('Streaming logs...')
        response = requests.get(self.url('commands', execution_id, 'logs'),
                                stream=True)
        check_status(response, requests.codes.ok)
        for line in response.raw:
            print(line.decode('utf-8'), end='')

    def cleanup(self, execution_id: str):
        log_info('Cleaning up all detritus.')
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


class CLIException(Exception):
    def __init__(self, message: str, cause: BaseException):
        self.message = message
        self.cause = cause

    def print(self, configuration):
        log_error(self.message)
        if configuration.debug:
            traceback.print_exception(
                type(self.cause), self.cause, self.cause.__traceback__)


COMMANDS = {
    'run': RunCommand,
}


def check_status(response, expected_status):
    if response.status_code != expected_status:
        raise RequestException(response)


def log_info(message):
    if sys.stdout.isatty():
        print('\x1b[33m', end='')
    print('=> ', end='')
    if sys.stdout.isatty():
        print('\x1b[0m', end='')
        print('\x1b[32m', end='')
    print(message, end='')
    if sys.stdout.isatty():
        print('\x1b[0m')


def log_error(message):
    isatty = sys.stdout.isatty()
    if isatty:
        print('\x1b[31m', end='')
    print('❗' if isatty else '!  ', message, end='')
    if isatty:
        print('\x1b[0m')


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
        if not command.run():
            sys.exit(1)
    except CLIException as e:
        e.print(configuration)
        sys.exit(1)


main(sys.argv[1:])
