import json
from json import JSONDecodeError
from typing import Any, Dict

from batman.cli.exceptions import CLIException

Parameters = Dict[str, Any]


def parse_file(path) -> Parameters:
    if path is None:
        return {}
    try:
        with open(path) as f:
            return parse_io(f, path)
    except FileNotFoundError as e:
        raise CLIException(
            f'The parameters file "{path}" does not exist.', e)


def parse_io(handle, path) -> Parameters:
    try:
        parameters = json.load(handle)
        if not isinstance(parameters, dict):
            raise CLIException(
                f'The parameters in "{path}" must be a JSON object.')
        return parameters
    except JSONDecodeError as e:
        raise CLIException(
            f'There was an error parsing "{path}".', e)
