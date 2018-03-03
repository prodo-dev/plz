import argparse
import json
import sys
import traceback
from typing import Optional, Tuple

import requests

from configuration import Configuration, ValidationException


class RunCommand:
    """Run an arbitrary command on a remote machine."""

    @staticmethod
    def prepare_argument_parser(parser):
        # TODO(sergio): build the Docker context as part of the command
        parser.add_argument('--bz2-file', required=True)
        parser.add_argument('command')

    def __init__(self, configuration, command, bz2_file):
        self.prefix = f'http://{configuration.host}:{configuration.port}'
        self.user = configuration.user
        self.project = configuration.project
        self.command = command
        self.bz2_file = bz2_file

    def run(self):
        snapshot_id = self.build_snapshot()
        if snapshot_id:
            execution_id, ok = self.issue_command(snapshot_id)
            try:
                if ok and execution_id:
                    self.display_logs(execution_id)
            except RequestException:
                log_error('Displaying the logs failed.')
                traceback.print_exc()
            if execution_id:
                self.cleanup(execution_id)
            log_info('Done and dusted.')

    def build_snapshot(self) -> Optional[str]:
        log_info('Building the program snapshot')
        metadata = json.dumps({
            'user': self.user,
            'project': self.project
        }).encode('utf-8')
        with open(self.bz2_file, 'rb') as f:
            file_content = f.read()
        request_data = b'\n'.join([metadata, file_content])
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
    def __init__(self, response):
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
    if sys.stdout.isatty():
        print('\x1b[31m', end='')
    print('❗', message, end='')
    if sys.stdout.isatty():
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
    command.run()


main(sys.argv[1:])
