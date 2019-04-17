from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, on_exception_reraise


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
        json_strings = self.controller.get_history(
            user=self.configuration.user,
            project=self.configuration.project)
        for s in json_strings:
            print(s, end='')

    def run(self):
        self.retrieve_history()
