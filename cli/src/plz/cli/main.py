import argparse
import os
import sys
from typing import Type

import pkg_resources

from plz.cli.configuration import Configuration, ValidationException
from plz.cli.describe_execution_operation import DescribeExecutionOperation
from plz.cli.exceptions import CLIException, ExitWithStatusCodeException
from plz.cli.kill_instances_operation import KillInstancesOperation
from plz.cli.last_execution_id_operation import LastExecutionIDOperation
from plz.cli.list_context_operation import ListContextOperation
from plz.cli.list_executions_operation import ListExecutionsOperation
from plz.cli.log import log_error, setup_logger
from plz.cli.logs_operation import LogsOperation
from plz.cli.operation import Operation
from plz.cli.ping_backend_operation import PingBackendOperation
from plz.cli.rerun_execution_operation import RerunExecutionOperation
from plz.cli.retrieve_history_operation import RetrieveHistoryOperation
from plz.cli.retrieve_measures_operation import RetrieveMeasuresOperation
from plz.cli.retrieve_output_operation import RetrieveOutputOperation
from plz.cli.run_execution_operation import RunExecutionOperation
from plz.cli.show_status_operation import ShowStatusOperation
from plz.cli.stop_execution_operation import StopExecutionOperation

OPERATIONS: [Type[Operation]] = [
    RunExecutionOperation,
    LogsOperation,
    ListExecutionsOperation,
    RetrieveOutputOperation,
    ShowStatusOperation,
    StopExecutionOperation,
    RetrieveHistoryOperation,
    RetrieveMeasuresOperation,
    PingBackendOperation,
    RerunExecutionOperation,
    ListContextOperation,
    KillInstancesOperation,
    DescribeExecutionOperation,
    LastExecutionIDOperation
]


def _get_version():
    if 'PLZ_OVERRIDE_VERSION' in os.environ:
        return os.environ['PLZ_OVERRIDE_VERSION']
    try:
        return pkg_resources.require('plz-cli')[0].version
    except pkg_resources.DistributionNotFound:
        # Not present in development
        return '0.x.0'


_build_timestamp = int(_get_version().split('.')[-1])


def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--ping-timeout', type=int, default=5)
    parser.add_argument('-c', '--configuration-path', type=str, default=None)
    subparsers = parser.add_subparsers(
        title='operations', dest='operation_name')
    for operation in OPERATIONS:
        subparser = subparsers.add_parser(
            operation.name(), help=operation.__doc__)
        operation.prepare_argument_parser(subparser, args)
    options = parser.parse_args(args)

    operation_name = options.operation_name
    if operation_name is None:
        parser.print_help()
        sys.exit(2)

    try:
        configuration_path = options.configuration_path \
                             or os.environ.get('PLZ_CONFIGURATION_PATH', None)
        configuration = Configuration.load(configuration_path, operation_name)
    except ValidationException as e:
        e.print()
        sys.exit(2)

    setup_logger(configuration)

    option_dict = options.__dict__
    del option_dict['operation_name']

    ping_timeout = options.ping_timeout
    if operation_name != 'ping-backend':
        del option_dict['ping_timeout']
    else:
        option_dict['build_timestamp'] = _build_timestamp

    del option_dict['configuration_path']

    operation_classes = [o for o in OPERATIONS if o.name() == operation_name]
    if len(operation_classes) == 0:
        log_error(
            'Internal error: couldn\'t find operation: '
            f'{operation_name}')
        sys.exit(os.EX_SOFTWARE)
    if len(operation_classes) > 1:
        log_error(
            'Internal error: more than one operation with name: '
            f'{operation_name}')
        sys.exit(os.EX_SOFTWARE)
    operation = operation_classes[0](
        configuration=configuration, **option_dict)
    try:
        if operation_name != 'ping-backend':
            # Ping the backend anyway as to avoid wasting user's time when the
            # backend is down
            PingBackendOperation(
                configuration,
                silent_on_success=True,
                ping_timeout=ping_timeout,
                build_timestamp=_build_timestamp).run()

        operation.run()
    except KeyboardInterrupt:
        log_error('Interrupted by the user.')
        sys.exit(1)
    except CLIException as e:
        e.print(configuration)
        sys.exit(e.exit_code)
    except ExitWithStatusCodeException as e:
        sys.exit(e.exit_code)


if __name__ == '__main__':
    main()
