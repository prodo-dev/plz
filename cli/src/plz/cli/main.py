import argparse
import sys
from typing import Dict, Type

from plz.cli.configuration import Configuration, ValidationException
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.list_commands_operation import ListCommandsOperation
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation
from plz.cli.run_command_operation import RunCommandOperation
from plz.cli.stop_command_operation import StopCommandOperation

OPERATIONS: Dict[str, Type[Operation]] = {
    'run': RunCommandOperation,
    'logs': LogsOperation,
    'list': ListCommandsOperation,
    'stop': StopCommandOperation,
}


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='operations',
                                       dest='operation_name')
    for name, command in OPERATIONS.items():
        subparser = subparsers.add_parser(name, help=command.__doc__)
        command.prepare_argument_parser(subparser, args)
    options = parser.parse_args(args)

    try:
        configuration = Configuration.load()
    except ValidationException as e:
        e.print()
        sys.exit(2)

    operation_name = options.operation_name
    option_dict = options.__dict__
    del option_dict['operation_name']

    command = OPERATIONS[operation_name](
        configuration=configuration, **option_dict)
    try:
        command.run()
    except CLIException as e:
        e.print(configuration)
        sys.exit(e.exit_code)
    except ExitWithStatusCodeException as e:
        sys.exit(e.exit_code)


if __name__ == '__main__':
    main()
