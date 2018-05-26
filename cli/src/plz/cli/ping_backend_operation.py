import json

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import ExitWithStatusCodeException
from plz.cli.log import log_error, log_info
from plz.cli.operation import Operation


class PingBackendOperation(Operation):
    @classmethod
    def name(cls):
        return 'ping-backend'

    @classmethod
    def prepare_argument_parser(cls, parser, args):
        parser.add_argument('-s', '--silent-on-success', action='store_true',
                            default=False)

    def __init__(self, configuration: Configuration, silent_on_success: bool,
                 ping_timeout: int):
        super().__init__(configuration)
        self.silent_on_success = silent_on_success
        self.ping_timeout = ping_timeout

    def run(self):
        response = requests.get(self.url('ping'), timeout=self.ping_timeout)
        is_ok = response.status_code == requests.codes.ok
        if is_ok and json.loads(response.content).get('plz', None) != 'pong':
            is_ok = False

        if is_ok:
            if not self.silent_on_success:
                log_info('Backend is reachable')
        else:
            log_error('Backend is unreachable')
            raise ExitWithStatusCodeException(1)
