from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import check_status, Operation


class StopCommandOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        if len(args) > 1:
            # Execution id was specified
            parser.add_argument(dest='execution_id')

    def __init__(self, configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    def run(self):
        response = requests.post(
            self.url('commands', self.get_execution_id(), 'stop'))
        check_status(response, requests.codes.no_content)
        log_info('Stopped')
