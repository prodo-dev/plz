import json
from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation


class DescribeExecutionOperation(Operation):
    """Print metadata about an execution"""

    @classmethod
    def name(cls):
        return 'describe'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)

    def __init__(self, configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    def run(self):
        description = self.controller.describe_execution_entrypoint(
            self.get_execution_id()
        )
        print(json.dumps(description['start_metadata'], indent=2))
