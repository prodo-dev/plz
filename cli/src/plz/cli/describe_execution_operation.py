import json
from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, check_status


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
        response = self.server.get(
            'executions', 'describe', self.get_execution_id(),
            stream=True)
        check_status(response, requests.codes.ok)
        print(json.dumps(response.json()['start_metadata'], indent=2))
