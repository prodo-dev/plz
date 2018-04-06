import traceback
from typing import Optional

from plz.cli.log import log_error


class CLIException(Exception):
    def __init__(self,
                 message: str,
                 cause: Optional[BaseException] = None,
                 exit_code: int = 1):
        self.message = message
        self.cause = cause
        self.exit_code = exit_code

    def print(self, configuration):
        log_error(self.message)
        if self.cause:
            print(self.cause)
            if configuration.debug:
                traceback.print_exception(
                    type(self.cause), self.cause, self.cause.__traceback__)


class ExitCodeException(Exception):
    def __init__(self, exit_code: int):
        self.exit_code = exit_code
