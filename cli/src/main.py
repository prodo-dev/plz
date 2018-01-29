import argparse
import requests
import sys


class RunCommand:
    '''Run an arbitrary command on a remote machine.'''

    @staticmethod
    def prepare_argument_parser(parser):
        parser.add_argument('command')

    def __init__(self, host, port, command):
        self.prefix = f'http://{host}:{port}'
        self.command = command

    def run(self):
        print(self.url('/'))
        self.issue_command()

    def issue_command(self):
        response = requests.post(self.url('/commands'), json={
            'command': self.command,
        })
        self.check_status(response, requests.codes.accepted)
        print(response.json())

    def check_status(self, response, expected_status):
        if response.status_code != expected_status:
            raise RequestException(response)

    def url(self, path):
        return self.prefix + path


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
