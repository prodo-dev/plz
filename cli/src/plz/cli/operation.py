import json
import os
from abc import ABC, abstractmethod

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException


class Operation(ABC):
    @classmethod
    @abstractmethod
    def name(cls):
        pass

    def __init__(self, configuration: Configuration):
        self.configuration = configuration
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

    @classmethod
    def maybe_add_execution_id_arg(cls, parser, args):
        # Positional arguments cannot be optional, so we check whether the
        # execution ID was specified and specify the argument only in that
        # case. Also display it when the user asks for help.
        try:
            idx = args.index(cls.name())
        except ValueError:
            # User is not calling this operation, include the execution_id as
            # it's helpful when the user is asking for help
            parser.add_argument('execution_id')
            return

        if idx + 1 < len(args) and (
                args[idx + 1][0] != '-' or args[idx + 1] in {'-h', '--help'}):
            parser.add_argument('execution_id')

    @classmethod
    @abstractmethod
    def prepare_argument_parser(cls, parser, args):
        pass

    @abstractmethod
    def run(self):
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


def add_output_dir_arg(parser):
    parser.add_argument('-o', '--output-dir',
                        type=str,
                        default=os.path.join(os.getcwd(), 'output/%e'),
                        help='Directory to store output. The string %e is '
                             'replaced by the execution id')
