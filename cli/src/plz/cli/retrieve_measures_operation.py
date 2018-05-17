from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.operation import Operation, check_status, \
    maybe_add_execution_id_arg, on_exception_reraise


class RetrieveMeasuresOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        maybe_add_execution_id_arg(parser, args)
        parser.add_argument('-s', '--summary', action='store_true')
        parser.set_defaults(summary=False)

    def __init__(self, configuration: Configuration, summary: bool,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.summary = summary
        self.execution_id = execution_id

    @on_exception_reraise('Retrieving the measures failed.')
    def retrieve_measures(self):
        response = requests.get(
            self.url('executions', self.get_execution_id(), 'measures'),
            params={'summary': self.summary})
        if response.status_code == requests.codes.conflict:
            raise CLIException(
                'Process is still running, run `plz stop` if you want to '
                'terminate it')
        check_status(response, requests.codes.ok)
        print(str(response.content, 'utf-8'))

    def run(self):
        self.retrieve_measures()
