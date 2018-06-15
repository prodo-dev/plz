from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, add_output_dir_arg
from plz.cli.run_execution_operation import RunExecutionOperation


class RerunExecutionOperation(Operation):
    """Check if the backend is reachable"""

    @classmethod
    def name(cls):
        return 'rerun'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        add_output_dir_arg(parser)

    def __init__(self, configuration: Configuration,
                 output_dir: str,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id
        self.output_dir = output_dir

    def run(self):
        response = self.server.post(
            'executions/rerun', stream=True,
            json={'user': self.configuration.user,
                  'project': self.configuration.project,
                  'execution_id': self.get_execution_id()})
        execution_id, ok = \
            RunExecutionOperation.get_execution_id_from_start_response(response)
        return RunExecutionOperation.follow_execution(
            execution_id, ok, self.configuration, self.output_dir,
            self.configuration.debug)
