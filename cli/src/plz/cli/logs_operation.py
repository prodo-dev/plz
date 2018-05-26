import time
from typing import Optional

import dateutil.parser
import requests

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation, check_status, \
    maybe_add_execution_id_arg, on_exception_reraise


class LogsOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        maybe_add_execution_id_arg(parser, args)
        parser.add_argument('-s', '--since')

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
            params = {'since': str(int(time.time()))}
        elif self.since == 'start':
            # Log from the beginning, that's the default for the backend
            params = {}
        else:
            try:
                since_timestamp = str(int(self.since))
            except ValueError:
                since_timestamp = str(int(time.mktime(
                    dateutil.parser.parse(self.since).timetuple())))
            params = {'since': since_timestamp}
        response = self.server.get(
            'executions', execution_id, 'logs',
            params=params,
            stream=True)
        check_status(response, requests.codes.ok)
        try:
            for line in response.raw:
                print(line.decode('utf-8'), end='')
        except KeyboardInterrupt:
            print()
            if print_interrupt_message:
                log_info('Your program is still running. '
                         'To stream the logs, type:\n\n'
                         f'        plz logs {execution_id}\n')
            raise
        print()

    def run(self):
        try:
            self.display_logs(self.get_execution_id())
        except KeyboardInterrupt:
            pass
