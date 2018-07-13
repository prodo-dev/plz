from typing import Optional

from plz.cli.configuration import Configuration
from plz.cli.log import log_info
from plz.cli.operation import Operation
from plz.controller.api.exceptions import ExecutionAlreadyHarvestedException


class StopExecutionOperation(Operation):
    """Stops an execution"""

    @classmethod
    def name(cls):
        return 'stop'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        cls.maybe_add_execution_id_arg(parser, args)

    def __init__(self, configuration: Configuration,
                 execution_id: Optional[str] = None):
        super().__init__(configuration)
        self.execution_id = execution_id

    def run(self):
        try:
            self.controller.delete_execution(
                execution_id=self.get_execution_id(),
                fail_if_running=False,
                fail_if_deleted=True)
        except ExecutionAlreadyHarvestedException:
            log_info('Process already stopped')
            return
        log_info('Stopped')
