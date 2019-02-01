from typing import Any, Optional

import dateutil.parser
import time

from plz.cli.composition_operation import CompositionOperation
from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import on_exception_reraise


class LogsOperation(CompositionOperation):
    """Output logs for a given execution"""

    @classmethod
    def name(cls):
        return 'logs'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        parser.add_argument(
            '-s', '--since',
            help='Specify a start time for the log output. Unfilled fields are'
                 'assumed to be same as of current time: `10:30` is today\'s '
                 '10:30. Use `start` to print all logs')

    def __init__(self,
                 configuration: Configuration,
                 since: Optional[str],
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id
        self.since = since

    @on_exception_reraise("Displaying the logs failed.")
    def display_logs(self, execution_id: str, print_interrupt_message=False):
        log_info('Streaming logs...')
        # For the since argument, pass an integer to the backend. Or nothing
        # in case we want to log from the start (so the default is different
        # in the cli --current time-- and the backend --start time--). That's
        # the easiest way to code it, as passing a datetime time object to the
        # backend would require to pass the timezone and doing timezone
        # calculations in the backend. This way all calculations
        # timezone-dependent calculations are done in in the cli and the
        # backend uses whatever timestamp we pass.
        if self.since is None:
            # Default: show since the current time
            since_timestamp = str(int(time.time()))
        elif self.since == 'start':
            # Log from the beginning, that's the default for the backend
            since_timestamp = None
        else:
            try:
                since_timestamp = str(int(self.since))
            except ValueError:
                since_timestamp = str(int(time.mktime(
                    dateutil.parser.parse(self.since).timetuple())))
        byte_lines = self.controller.get_logs(
            self.get_execution_id(), since=since_timestamp)
        try:
            for byte_line in byte_lines:
                print(byte_line.decode('utf-8'), end='', flush=True)
        except KeyboardInterrupt:
            print()
            if print_interrupt_message:
                log_info('Your program is still running. '
                         'To stream the logs, type:\n\n'
                         f'        plz logs {execution_id}\n')
            raise
        print()

    def run_atomic(
            self, atomic_execution_id: str, composition_path: [(str, Any)]):
        if len(composition_path) > 0:
            raise NotImplementedError(
                'Logs for parallel executions are not implemented')
        try:
            self.display_logs(atomic_execution_id)
        except KeyboardInterrupt:
            pass
