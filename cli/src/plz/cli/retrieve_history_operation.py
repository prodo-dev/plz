import requests

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, check_status, \
    on_exception_reraise


class RetrieveHistoryOperation(Operation):
    @staticmethod
    def prepare_argument_parser(parser, args):
        pass

    def __init__(self, configuration: Configuration):
        super().__init__(configuration)

    @on_exception_reraise('Retrieving the output failed.')
    def retrieve_history(self):
        response = requests.get(
            self.url('executions', self.configuration.user,
                     self.configuration.project, 'history'),
            stream=True)
        check_status(response, requests.codes.ok)
        for r in response.raw:
            print(r.decode('utf-8'), end='')

    def run(self):
        self.retrieve_history()
