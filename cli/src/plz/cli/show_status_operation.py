import collections
import os
from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation, check_status, on_exception_reraise

ExecutionStatus = collections.namedtuple(
    'ExecutionStatus',
    ['running', 'success', 'code'])


class ShowStatusOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        if len(args) > 1:
            # Execution ID was specified
            parser.add_argument(dest='execution_id')

    def __init__(self, configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    @on_exception_reraise('Retrieving the status failed.')
    def get_status(self):
        response = requests.get(
            self.url('executions', self.get_execution_id(), 'status'))
        check_status(response, requests.codes.ok)
        body = response.json()
        return ExecutionStatus(
            running=body['running'],
            success=body['success'],
            code=body['exit_status'])

    def run(self):
        log_info(f'{self.get_status()}')
