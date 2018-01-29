import logging
from collections import Generator

import requests
import shlex
import subprocess

import select
from flask import Flask, Response, jsonify, request, stream_with_context
from types import GeneratorType

_LOGGER = logging.getLogger('controller')


app = Flask(__name__)


_COMMANDS_ROUTE = 'commands'
_LOGS_SUBROUTE = 'logs'


@app.route(f'/{_COMMANDS_ROUTE}', methods=['POST'])
def run_command_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/commands
    command = request.json['command']
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


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}',
           methods=['GET'])
def get_output_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs
    # TODO(sergio): use the execution id instead of the container id
    container_id = execution_id
    return _stream_binary_generator(get_logs_of_container(container_id))


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stdout')
def get_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stdout
    # TODO(sergio): do the real thing
    container_id = execution_id
    return _stream_binary_generator(get_logs_of_container(container_id))


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stderr')
def get_stderr_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    # TODO(sergio): do the real thing
    container_id = execution_id
    return _stream_binary_generator(get_logs_of_container(container_id))


def get_output(execution_id: str) -> GeneratorType:
    # TODO(sergio): do the actual thing
    for i in execution_id:
        yield i


def check_is_container_id(container_id: str):
    if len(container_id) != 64:
        return False
    try:
        int(container_id, 16)
    except ValueError:
        return False
    return True


def run_command_and_return_container_id(command):
    # TODO(sergio): do not hardcode machine/image
    p = subprocess.Popen([
        'ssh', 'ubuntu@34.243.203.81',
        'docker', 'run', '-d',
        '024444204267.dkr.ecr.eu-west-1.amazonaws.com/ml-pytorch',
        'bash', '-c', f'{shlex.quote(command)}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    stdout, stderr = p.communicate()

    container_id = stdout.rstrip('\n')

    if stderr != '' or p.returncode != 0 or \
            not check_is_container_id(container_id):
        raise ControllerException(
            f'Error running command\n'
            f'Exit code: [{p.returncode}]\n'
            f'Stdout is [{stdout}]\n'
            f'Stderr is [{stderr}]\n')
    _LOGGER.info(f'Container id is: {container_id}')
    return container_id


def get_logs_of_container(container_id):
    p = None
    try:
        # TODO(sergio): do not hardcode machine/image
        p = subprocess.Popen(
            ['bash', '-c',
             'ssh ubuntu@34.243.203.81 '
             f'\'docker logs {container_id} -f 2>&1\''],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        # Note: the docs indicate to use p.communicate() instead of
        # p.stdout and p.stderr due to the possibility of deadlocks. As far I
        # understand the problem occurs when the internal buffers are full,
        # causing the child process to block (which in our case is not a
        # problem). See here:
        # https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging
        # -PIPE-is-your-enemy/
        # We cannot it use communicate as it waits for the process to finish.
        # An alternative would be to use a tempfile.TemporaryFile
        # https://docs.python.org/3/library/tempfile.html
        # Do not use this code in other parts if you don't want the child to
        # block
        out = None
        stderr = None
        while out is None or len(out):
            out = p.stdout.read1(1024)
            # Poll stderr to see if there's something
            stderr_to_read, _, _ = select.select(
                [p.stderr.fileno()], [], [], 0.1)
            if stderr_to_read:
                # Check the length, if the process is already finished we
                # might be reading the empty bytes, and there was no error
                stderr = p.stderr.read()
                if len(stderr):
                    raise ControllerException(
                        f'Error running command\n'
                        f'Exit code: [{p.returncode}]\n'
                        f'Stdout is [{out}]\n'
                        f'Stderr is [{stderr}]\n')
            yield(out)
        # Get the return code
        try:
            p.communicate(timeout=0.01)
        except subprocess.TimeoutExpired:
            pass
        if p.returncode is None or p.returncode != 0:
            raise ControllerException(
                f'Error running command\n'
                f'Exit code: [{p.returncode}]\n'
                f'Stdout is [{out}]\n'
                f'Stderr is [{stderr}]\n')
    finally:
        if p is not None and p.returncode is None:
            p.kill()


def _stream_binary_generator(generator: Generator) -> Response:
    return Response(stream_with_context(generator),
                    mimetype='application/octet-stream')


class ControllerException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


app.run()
