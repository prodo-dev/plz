import json
import os
from abc import ABC, abstractmethod

import requests

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.server import Server


class Operation(ABC):
    @classmethod
    @abstractmethod
    def name(cls):
        pass

    def __init__(self, configuration: Configuration):
        self.configuration = configuration
        self.server = Server.from_configuration(configuration)
        self.user = configuration.user
        self.execution_id = None

    def get_execution_id(self):
        if self.execution_id is not None:
            return self.execution_id
        response = self.server.get(
            'users', self.user, 'last_execution_id')
        check_status(response, requests.codes.ok)
        response_object = json.loads(response.content)
        if 'execution_id' in response_object:
            return response_object['execution_id']
        else:
            raise ValueError('Expected an execution ID')

    @classmethod
    def maybe_add_execution_id_arg(cls, parser, args):
        # Positional arguments cannot be optional, but we don't want the user
        # to type it each time. If the user is doing simply
        # `plz operation [other_args]` we do
        # not add the argument, unless the user is asking for help
        add_arg = True
        if len(args) > 0 and args[0] == cls.name():
            if len(args) == 1:
                add_arg = False
            else:
                if args[1][0] == '-' and not args[1] in {'-h', '--help'}:
                    add_arg = False
        if add_arg:
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
                raise CLIException(message) from cause

        return wrapped

    return wrapper


def add_output_dir_arg(parser):
    parser.add_argument('-o', '--output-dir',
                        type=str,
                        default=os.path.join(os.getcwd(), 'output/%e'),
                        # Note, it's actually the string `%e`, the argparser
                        # lib does string replacement the old Python 2 way...
                        help='Directory to store output. The string %%e is '
                             'replaced by the execution id')
