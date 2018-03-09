import traceback
from typing import Optional

from log import log_error


class CLIException(Exception):
    def __init__(self, message: str, cause: Optional[BaseException] = None):
        self.message = message
        self.cause = cause

    def print(self, configuration):
        log_error(self.message)
        if self.cause:
            print(self.cause)
            if configuration.debug:
                traceback.print_exception(
                    type(self.cause), self.cause, self.cause.__traceback__)
