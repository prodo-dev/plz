import traceback

import requests

from plz.cli.log import log_error


class ExitWithStatusCodeException(Exception):
    def __init__(self, exit_code: int):
        self.exit_code = exit_code


class CLIException(ExitWithStatusCodeException):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(exit_code)
        self.message = message

    def print(self, configuration):
        log_error(self.message)
        cause = self.__cause__
        if cause:
            print(cause)
            if configuration.debug:
                traceback.print_exception(type(cause),
                                          cause,
                                          cause.__traceback__)


class RequestException(Exception):
    def __init__(self, response: requests.Response):
        try:
            body = response.json()
        except ValueError:
            body = response.text
        super().__init__(
            f'Request failed with status code {response.status_code}.\n' +
            f'Response:\n{body}')
