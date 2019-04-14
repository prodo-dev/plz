from typing import Optional

from plz.cli import parameters

from plz.cli.configuration import Configuration
from plz.cli.operation import Operation, add_output_dir_arg
from plz.cli.run_execution_operation import RunExecutionOperation, \
    add_detach_command_line_argument, create_instance_market_spec


class RerunExecutionOperation(Operation):
    """Rerun an execution given an execution ID"""

    @classmethod
    def name(cls):
        return 'rerun'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)
        add_detach_command_line_argument(parser)
        add_output_dir_arg(parser)
        parser.add_argument('-p',
                            '--override-parameters',
                            dest='parameters_file',
                            help='Override the parameters of the previous '
                            'run with the ones in this file',
                            type=str,
                            default=None)

    def __init__(self,
                 configuration: Configuration,
                 output_dir: str,
                 detach: bool,
                 parameters_file: Optional[str],
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.detach = detach
        self.execution_id = execution_id
        self.output_dir = output_dir
        self.parameters_file = parameters_file

    def run(self):
        run_operation = RunExecutionOperation(self.configuration,
                                              command=None,
                                              output_dir=self.output_dir,
                                              parameters_file=None,
                                              detach=self.detach)
        instance_max_uptime_in_minutes = \
            self.configuration.instance_max_uptime_in_minutes
        if self.parameters_file is not None:
            override_parameters = parameters.parse_file(self.parameters_file)
        else:
            override_parameters = None
        response_dicts = self.controller.rerun_execution(
            user=self.configuration.user,
            project=self.configuration.project,
            instance_max_uptime_in_minutes=instance_max_uptime_in_minutes,
            previous_execution_id=self.get_execution_id(),
            instance_market_spec=create_instance_market_spec(
                self.configuration),
            override_parameters=override_parameters)

        new_execution_id, was_start_ok = \
            RunExecutionOperation.get_execution_id_from_start_response(
                response_dicts)
        run_operation.execution_id = new_execution_id
        run_operation.follow_execution(was_start_ok)
