import argparse
import os
import sys
import threading

from collections import namedtuple
from distutils.util import strtobool

_ARGUMENTS_SPEC = [
    {
        'name': 'aws_project',
        'spec': {
            'type': str,
            'help': 'AWS project in the Elastic Container Registry. '
                    'Example: 024444204267.dkr.ecr.eu-west-1.amazonaws.com',
        },
    },
    {
        'name': 'aws_worker_ami',
        'spec': {
            'type': str,
            'help': 'AWS AMI used for constructing worker instances. '
                    'Example: plz-worker-2018-01-01',
        },
    },
    {
        'name': 'aws_key_name',
        'spec': {
            'type': str,
            'help': 'AWS key pair for debugging worker instances. '
                    'Example: plz-production-key',
        },
        'default': None,
    },
    {
        'name': 'environment_name',
        'spec': {
            'type': str,
            'help': 'Name used to identify the resources used by this'
                    'controller. '
                    'Example: production, sergio',
        },
    },
    {
        'name': 'docker_host',
        'spec': {
            'type': str,
            'help': 'url pointing at the docker server. '
                    'Example: tcp://127.0.0.1:1234'
        },
        'default': None,
    },
    {
        'name': 'port',
        'spec': {
            'type': int,
            'help': 'port where the controller listens for HTTP requests',
        },
        'default': 8080,
    },
    {
        'name': 'run_executions_locally',
        'spec': {
            'action': 'store_const',
            'const': True,
            'help': 'don\'t spawn workers, run the executions locally',
        },
        'from_string': strtobool,
        'default': False,
    },
    {
        'name': 'data_dir',
        'spec': {
            'type': str,
            'help': 'Directory to store input data',
        },
    }
]
_CONFIG_LOCK = threading.Lock()

Config = namedtuple('Config', [spec['name'] for spec in _ARGUMENTS_SPEC])


def _create_arg_parser():
    arg_parser = argparse.ArgumentParser(
        description='Controller for plz workers')
    for spec in _ARGUMENTS_SPEC:
        arg_parser.add_argument(f'--{_name_to_cli_parameter(spec["name"])}',
                                **spec['spec'])
    return arg_parser


def _name_to_cli_parameter(name: str):
    return name.replace('_', '-')


def _name_to_env_variable(name: str):
    return name.upper()


def _create_config():
    cfg = {}
    arg_parser = _create_arg_parser()
    if '--' in sys.argv:
        arg_start = sys.argv.index('--') + 1
        raw_args = sys.argv[arg_start:]
    else:
        raw_args = sys.argv[1:]
    args = arg_parser.parse_args(raw_args)
    for spec in _ARGUMENTS_SPEC:
        val = getattr(args, spec['name'], None)
        if val is None:
            val = os.environ.get(_name_to_env_variable(spec['name']), None)
            if val is not None:
                if 'from_string' in spec:
                    # noinspection PyCallingNonCallable
                    val = spec['from_string'](val)
                elif 'type' in spec['spec']:
                    val = spec['spec']['type'](val)
        if val is None:
            if 'default' in spec:
                val = spec['default']
            else:
                raise KeyError(
                    'Parameter wasn\'t specified and there\'s no default: '
                    f'--{_name_to_cli_parameter(spec["name"])}')
        cfg[spec['name']] = val
    return Config(**cfg)


config = _create_config()
