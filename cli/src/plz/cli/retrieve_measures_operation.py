from typing import Any, List, Optional, Tuple

from plz.cli.composition_operation import CompositionOperation, \
    create_path_string_prefix
from plz.cli.configuration import Configuration
from plz.cli.operation import on_exception_reraise


class RetrieveMeasuresOperation(CompositionOperation):
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
    def retrieve_measures(
            self,
            atomic_execution_id: Optional[str] = None,
            composition_path: Optional[List[Tuple[str, Any]]] = None):
        if atomic_execution_id is None:
            atomic_execution_id = self.get_execution_id()
        if len(composition_path) > 0:
            index = int(composition_path[-1][1])
        else:
            index = None
        json_strings = self.controller.get_measures(
            execution_id=atomic_execution_id,
            summary=self.summary,
            index=index)
        for line in json_strings:
            print(create_path_string_prefix(composition_path) + line, end='')

    def run_atomic(
            self, atomic_execution_id: str, composition_path: [(str, Any)]):
        self.retrieve_measures(atomic_execution_id, composition_path)
