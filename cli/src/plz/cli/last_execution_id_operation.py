import sys

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.operation import Operation


class LastExecutionIDOperation(Operation):
    """Print the last execution id."""

    @classmethod
    def name(cls):
        return 'last'

    def __init__(self, configuration: Configuration):
        super().__init__(configuration)

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        pass

    def run(self):
        execution_id = self.get_execution_id()
        if execution_id is None or execution_id == '':
            raise CLIException('No execution ID for this user!')
        print(self.get_execution_id(), end='\n' if sys.stdout.isatty() else '')
