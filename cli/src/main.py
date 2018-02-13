import argparse
import json
from typing import Optional

import requests
import sys


class RunCommand:
    '''Run an arbitrary command on a remote machine.'''

    @staticmethod
    def prepare_argument_parser(parser):
        parser.add_argument('command')
        # TODO(sergio): grab user and project from somewhere
        parser.add_argument('--user')
        parser.add_argument('--project')
        # TODO(sergio): gather the files and zip instead of passing
        # the parameter
        parser.add_argument('--bz2-file')

    def __init__(self, host, port, command, user, project, bz2_file):
        self.prefix = f'http://{host}:{port}'
        self.command = command
        self.user = user
        self.project = project
        self.bz2_file = bz2_file

    def run(self):
        snapshot = self.build_snapshot()
        process = self.issue_command(snapshot)
        self.display_logs({
            'command': self.command,
            'snapshot': snapshot
        })
        self.cleanup(process)

    def build_snapshot(self) -> Optional[str]:
        metadata = json.dumps({
            'user': self.user,
            'project': self.project
        }).encode('utf-8')
        with open(self.bz2_file, 'rb') as f:
            file_content = f.read()
        request_data = b'\n'.join([metadata, file_content])
        response = requests.post(
            self.url('snapshots'), request_data, stream=True)
        self.check_status(response, requests.codes.ok)
        error = False
        snapshot = None
        for json_bytes in response.raw:
            json_resp = json.loads(str(json_bytes, 'utf-8'))
            if 'stream' in json_resp:
                print(json_resp['stream'], end='')
            if 'error' in json_resp:
                error = True
                print(json_resp['error'], end='', file=sys.stdout)
            if 'aux' in json_resp:
                snapshot = json_resp['aux']['ID']
        if error:
            return None
        return snapshot

    def issue_command(self, snapshot):
        response = requests.post(self.url('commands'), json={
            'command': self.command,
            'snapshot': snapshot
        })
        self.check_status(response, requests.codes.accepted)
        return response.json()

    def display_logs(self, process):
        response = requests.get(self.url('commands', process['id'], 'logs'),
                                stream=True)
        self.check_status(response, requests.codes.ok)
        for line in response.raw:
            print(line.decode('utf-8'), end='')

    def cleanup(self, process):
        response = requests.delete(self.url('commands', process['id']))
        self.check_status(response, requests.codes.no_content)

    def check_status(self, response, expected_status):
        if response.status_code != expected_status:
            raise RequestException(response)

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


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=80)
    subparsers = parser.add_subparsers(title='commands', dest='command_name')
    for name, command in COMMANDS.items():
        subparser = subparsers.add_parser(name, help=command.__doc__)
        command.prepare_argument_parser(subparser)
    options = parser.parse_args(args)
    command_name = options.command_name
    option_dict = options.__dict__
    del option_dict['command_name']
    command = COMMANDS[command_name](**option_dict)
    command.run()


main(sys.argv[1:])
