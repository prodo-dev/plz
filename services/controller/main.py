import logging
import requests
import subprocess

from flask import Flask, jsonify, request, Response
from types import GeneratorType

_LOGGER = logging.getLogger('controller')


app = Flask(__name__)


_COMMAND_ROUTE = 'command'
_LOGS_SUBROUTE = 'logs'


@app.route(f'/{_COMMAND_ROUTE}', methods=['POST'])
def run_command_entrypoint():
    # Test with:
    # curl -X POST -F 'command=ls' localhost:5000/command
    command = request.form['command']
    resp = jsonify({'id': run_command(command)})
    resp.status_code = requests.codes.accepted
    return resp


def run_command(command: str) -> str:
    """
    Runs a command in a machine.

    Returns a unique id for the command execution, that can be passed to other
    entrypoints as to retrieve information about the execution

    :param command: command to run with 'bash -c'
    :return: unique execution id
    """
    # TODO(sergio): return an id for the execution, not the container id
    return run_command_and_return_container_id(command)


@app.route(f'/{_COMMAND_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}',
           methods=['GET'])
def get_output_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/command/some-id/logs
    return _stream_binary_generator(get_output(execution_id))


@app.route(f'/{_COMMAND_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stdout')
def get_stderr_entrypoint(execution_id):
    # Test with:
    # curl -X POST -F 'command=ls' localhost:5000/command/some-id/logs/stdout
    return _stream_binary_generator(get_output(execution_id))


@app.route(f'/{_COMMAND_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stderr')
def get_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/command/some-id/logs/stderr
    return _stream_binary_generator(get_output(execution_id))


def get_output(execution_id: str) -> GeneratorType:
    # TODO(sergio): do the actual thing
    for i in execution_id:
        yield i


def run_command_and_return_container_id(command):
    # TODO(sergio): do not hardcode machine/image
    p = subprocess.Popen([
        'ssh', 'ubuntu@34.244.128.112',
        'docker', 'run', '-d',
        '024444204267.dkr.ecr.eu-west-1.amazonaws.com/ml-pytorch',
        'bash', '-c', command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    stdout, stderr = p.communicate()

    is_hex_string = True
    try:
        int(stdout.rstrip('\n'), 16)
    except ValueError:
        is_hex_string = False

    if stderr != '' or p.returncode != 0 or not is_hex_string:
        raise ControllerException(
            f'Error running command\n'
            f'Exit code: [{p.returncode}]\n'
            f'Stdout is [{stdout}]\n'
            f'Stderr is [{stderr}]\n')
    _LOGGER.info(f'Container id is: {stdout}')
    return stdout.rstrip('\n')


def _stream_binary_generator(generator: GeneratorType) -> Response:
    return Response(generator, mimetype='application/octet-stream')


class ControllerException(Exception):
    def __init__(self, msg):
        super().__init__(msg)

app.run()
