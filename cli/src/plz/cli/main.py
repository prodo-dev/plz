import argparse
import sys
from typing import Dict, Type

from plz.cli.configuration import Configuration, ValidationException
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.list_executions_operation import ListExecutionsOperation
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation
from plz.cli.run_execution_operation import RunExecutionOperation
from plz.cli.stop_execution_operation import StopExecutionOperation

OPERATIONS: Dict[str, Type[Operation]] = {
    'run': RunExecutionOperation,
    'logs': LogsOperation,
    'list': ListExecutionsOperation,
    'stop': StopExecutionOperation,
}


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='operations',
                                       dest='operation_name')
    for name, operation in OPERATIONS.items():
        subparser = subparsers.add_parser(name, help=operation.__doc__)
        operation.prepare_argument_parser(subparser, args)
    options = parser.parse_args(args)

    try:
        configuration = Configuration.load()
    except ValidationException as e:
        e.print()
        sys.exit(2)

    operation_name = options.operation_name
    option_dict = options.__dict__
    del option_dict['operation_name']

    operation = OPERATIONS[operation_name](
        configuration=configuration, **option_dict)
    try:
        operation.run()
    except CLIException as e:
        e.print(configuration)
        sys.exit(e.exit_code)
    except ExitWithStatusCodeException as e:
        sys.exit(e.exit_code)


if __name__ == '__main__':
    main()
