#encoding utf-8
import argparse
import sys
import threading

from os import environ

AWS_PROJECT = 'aws-project'
DOCKER_HOST = 'docker-host'
PORT = 'port'

_ARGUMENTS_SPEC = [
    {
        'name': AWS_PROJECT,
        'spec': {
            'type': str,
            'help': 'project in the Elastic Container Registry. '
                    'Example: 024444204267.dkr.ecr.eu-west-1.amazonaws.com'
        },
        'default': None
    },
    {
        'name': DOCKER_HOST,
        'spec': {
            'type': str,
            'help': 'url pointing at the docker server. Example: tcp://127.0.0.1:1234'
        },
        'default': None
    },
    {
        'name': PORT,
        'spec': {
            'type': int,
            'help': 'port where the controller listens for HTTP requests'
        },
        'default': 8080
    }

]
_CONFIG_LOCK = threading.Lock()


def _create_arg_parser():
    arg_parser = argparse.ArgumentParser(description = 'Controller for batman workers')
    for spec in _ARGUMENTS_SPEC:
        arg_parser.add_argument(f'--{spec["name"]}', **spec['spec'])
    return arg_parser


def _name_to_attr(name: str):
    return name.replace('-', '_')


def _name_to_env_variable(name: str):
    return name.replace('-', '_').upper()


def _create_config():
    config = {}
    arg_parser = _create_arg_parser()
    args = arg_parser.parse_args(sys.argv[1:])
    for spec in _ARGUMENTS_SPEC:
        val = getattr(args, _name_to_attr(spec['name']), None)
        if val is None:
            val = environ.get(_name_to_env_variable(spec['name']), None)
        config[spec['name']] = val
    return config


_config = None


def get_config_parameter(name: str):
    global _config
    if _config is None:
        with _CONFIG_LOCK:
            if _config is None:
                _config = _create_config()
    return _config[name]
