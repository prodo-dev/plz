import json
from typing import Any, Optional

from plz.cli.composition_operation import CompositionOperation, \
    create_path_string_prefix
from plz.cli.configuration import Configuration


class DescribeExecutionOperation(CompositionOperation):
    """Print metadata about an execution"""

    @classmethod
    def name(cls):
        return 'describe'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)

    def __init__(self,
                 configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    def run_atomic(self, atomic_execution_id: str,
                   composition_path: [(str, Any)]):
        description = self.controller.describe_execution_entrypoint(
            atomic_execution_id)
        description_str = json.dumps(description['start_metadata'], indent=2)
        for l in description_str.splitlines():
            print(create_path_string_prefix(composition_path) + l)
