import argparse
import sys


class RunCommand:
    '''Run an arbitrary command on a remote machine.'''

    @staticmethod
    def prepare_argument_parser(parser):
        parser.add_argument('command')

    def __init__(self, host, command):
        self.host = host
        self.command = command

    def run(self):
        print(self.command)


COMMANDS = {
    'run': RunCommand,
}


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--host')
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
