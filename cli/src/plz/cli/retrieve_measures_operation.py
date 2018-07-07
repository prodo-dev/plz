from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, on_exception_reraise


class RetrieveMeasuresOperation(Operation):
    """Output measures for an execution"""

    @classmethod
    def name(cls):
        return 'measures'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        parser.add_argument('-s', '--summary', action='store_true',
                            help='Retrieve only the summary measures')
        parser.set_defaults(summary=False)

    def __init__(self, configuration: Configuration, summary: bool,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.summary = summary
        self.execution_id = execution_id

    @on_exception_reraise('Retrieving the measures failed.')
    def retrieve_measures(self):
        json_strings = self.controller.get_measures(
            execution_id=self.get_execution_id(),
            summary=self.summary)
        for line in json_strings:
            print(line, end='')

    def run(self):
        self.retrieve_measures()
