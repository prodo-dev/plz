from plz.cli.configuration import Configuration
from plz.cli.exceptions import ExitWithStatusCodeException
from plz.cli.log import log_error, log_info
from plz.cli.operation import Operation


class PingBackendOperation(Operation):
    """Check if the backend is reachable"""

    @classmethod
    def name(cls):
        return 'ping-backend'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument('-s', '--silent-on-success', action='store_true',
                            default=False,
                            help='On success exit with 0 and no output. '
                                 'Useful for scripts')

    def __init__(self, configuration: Configuration, silent_on_success: bool,
                 ping_timeout: int):
        super().__init__(configuration)
        self.silent_on_success = silent_on_success
        self.ping_timeout = ping_timeout

    def run(self):
        response_dict = self.controller.ping(self.ping_timeout)
        if response_dict.get('plz', None) == 'pong':
            if not self.silent_on_success:
                log_info('Backend is reachable')
        else:
            log_error('Backend is unreachable')
            raise ExitWithStatusCodeException(1)
