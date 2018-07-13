import collections
from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation, on_exception_reraise

ExecutionStatus = collections.namedtuple(
    'ExecutionStatus',
    ['running', 'success', 'code'])


class ShowStatusOperation(Operation):
    """Output the status of an execution"""

    @classmethod
    def name(cls):
        return 'status'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)

    def __init__(self, configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    @on_exception_reraise('Retrieving the status failed.')
    def get_status(self):
        status = self.controller.get_status(self.get_execution_id())
        return ExecutionStatus(
            running=status['running'],
            success=status['success'],
            code=status['exit_status'])

    def run(self):
        status = self.get_status()
        log_info('Status:')
        print('Running:', status.running)
        print('Success:', status.success)
        print('Exit Status:', status.code)
