from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, add_output_dir_arg
from plz.cli.run_execution_operation import RunExecutionOperation


class RerunExecutionOperation(Operation):
    """Rerun an execution given an execution ID"""

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
        run_operation = RunExecutionOperation(
            self.configuration, command=None, output_dir=self.output_dir,
            parameters_file=None)
        response_dicts = self.controller.rerun_execution(
            user=self.configuration.user,
            project=self.configuration.project,
            previous_execution_id=self.get_execution_id(),
            instance_market_spec=run_operation.get_instance_market_spec())

        new_execution_id, was_start_ok = \
            RunExecutionOperation.get_execution_id_from_start_response(
                response_dicts)
        run_operation.execution_id = new_execution_id
        run_operation.follow_execution(was_start_ok)
