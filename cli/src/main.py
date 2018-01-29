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
        process = self.issue_command()
        self.display_logs(process)
        self.cleanup(process)

    def issue_command(self):
        response = requests.post(self.url('commands'), json={
            'command': self.command,
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
