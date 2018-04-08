from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation, check_status, on_exception_reraise


class LogsOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        # Positional arguments cannot be optional, so we check whether the
        # execution ID was specified and specify the argument only in that
        # case
        if len(args) > 1:
            parser.add_argument('execution_id')

    def __init__(self,
                 configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    @on_exception_reraise("Displaying the logs failed.")
    def display_logs(self, execution_id: str):
        log_info('Streaming logs...')
        response = requests.get(self.url('executions', execution_id, 'logs'),
                                stream=True)
        check_status(response, requests.codes.ok)
        try:
            for line in response.raw:
                print(line.decode('utf-8'), end='')
        except KeyboardInterrupt:
            print()
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
