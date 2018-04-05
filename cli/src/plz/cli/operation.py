import json
from abc import ABC, abstractmethod
from typing import Optional

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException


class Operation(ABC):
    def __init__(self, configuration: Configuration):
        self.prefix = f'http://{configuration.host}:{configuration.port}'
        self.user = configuration.user
        self.execution_id = None

    def url(self, *path_segments: str):
        return self.prefix + '/' + '/'.join(path_segments)

    def get_execution_id(self):
        if self.execution_id is not None:
            return self.execution_id
        response = requests.get(
            self.url('users', self.user, 'last_execution_id'))
        check_status(response, requests.codes.ok)
        response_object = json.loads(response.content)
        if 'execution_id' in response_object:
            return response_object['execution_id']
        else:
            raise ValueError('Expected an execution ID')

    @staticmethod
    @abstractmethod
    def prepare_argument_parser(parser, args):
        pass

    @abstractmethod
    def run(self) -> Optional[int]:
        pass


class RequestException(Exception):
    def __init__(self, response: requests.Response):
        try:
            body = response.json()
        except ValueError:
            body = response.text
        super().__init__(
            f'Request failed with status code {response.status_code}.\n' +
            f'Response:\n{body}'
        )


def check_status(response: requests.Response, expected_status: int):
    if response.status_code != expected_status:
        raise RequestException(response)


def on_exception_reraise(message: str):
    def wrapper(f):
        def wrapped(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except Exception as cause:
                raise CLIException(message, cause)

        return wrapped

    return wrapper
