#encoding utf-8
import argparse
import sys
import threading

from os import environ

DOCKER_HOST = 'docker-host'

_ARGUMENTS_SPEC = [
    {
     'name': DOCKER_HOST,
     'spec': {
        'type': str,
        'help': 'url pointing at the docker server. Example: tcp://127.0.0.1:1234'
     },
     'default': None
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
