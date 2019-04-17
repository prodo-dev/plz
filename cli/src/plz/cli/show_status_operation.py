import collections
from typing import Any, Optional

from plz.cli.composition_operation import CompositionOperation, \
    create_path_string_prefix
from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import on_exception_reraise

ExecutionStatus = collections.namedtuple('ExecutionStatus',
                                         ['running',
                                          'success',
                                          'code'])


class ShowStatusOperation(CompositionOperation):
    """Output the status of an execution"""
    @classmethod
    def name(cls):
        return 'status'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)

    def __init__(self,
                 configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    @on_exception_reraise('Retrieving the status failed.')
    def get_status(self, atomic_execution_id: Optional[str] = None):
        if atomic_execution_id is None:
            atomic_execution_id = self.get_execution_id()
        status = self.controller.get_status(atomic_execution_id)
        return ExecutionStatus(running=status['running'],
                               success=status['success'],
                               code=status['exit_status'])

    def run_atomic(self,
                   atomic_execution_id: str,
                   composition_path: [(str,
                                       Any)]):
        status = self.get_status(atomic_execution_id)
        string_prefix = create_path_string_prefix(composition_path)
        log_info(f'{string_prefix}Status:')
        print('Running:', status.running)
        print('Success:', status.success)
        print('Exit Status:', status.code)
