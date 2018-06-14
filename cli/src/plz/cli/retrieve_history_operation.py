import requests

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, check_status, \
    on_exception_reraise


class RetrieveHistoryOperation(Operation):
    """Output json describing finished executions for user and project"""

    @classmethod
    def name(cls):
        return 'history'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        pass

    def __init__(self, configuration: Configuration):
        super().__init__(configuration)

    @on_exception_reraise('Retrieving the history failed.')
    def retrieve_history(self):
        response = self.server.get(
            'executions',
            self.configuration.user,
            self.configuration.project,
            'history',
            stream=True)
        check_status(response, requests.codes.ok)
        for r in response.raw:
            print(r.decode('utf-8'), end='')

    def run(self):
        self.retrieve_history()
