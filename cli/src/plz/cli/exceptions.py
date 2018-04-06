import traceback
from typing import Optional

from plz.cli.log import log_error


class ExitWithStatusCodeException(Exception):
    def __init__(self, exit_code: int):
        self.exit_code = exit_code


class CLIException(ExitWithStatusCodeException):
    def __init__(self,
                 message: str,
                 cause: Optional[BaseException] = None,
                 exit_code: int = 1):
        super().__init__(exit_code)
        self.message = message
        self.cause = cause

    def print(self, configuration):
        log_error(self.message)
        if self.cause:
            print(self.cause)
            if configuration.debug:
                traceback.print_exception(
                    type(self.cause), self.cause, self.cause.__traceback__)
