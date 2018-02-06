# coding=utf-8
import docker
import json
import logging
import random
import requests
import select
import shlex
import socket
import subprocess
import time
import uuid

from collections import Generator
from flask import Flask, Response, jsonify, request, stream_with_context

from AutoScalingGroup import AutoScalingGroup

_COMMANDS_ROUTE = 'commands'
_LOGS_SUBROUTE = 'logs'

_LOGGER = logging.getLogger('controller')
_DOCKER_CLIENT = docker.from_env()

app = Flask(__name__)


# TODO: set autoscaling group properly
_AUTOSCALING_GROUP = AutoScalingGroup.get_group('batman-worker')


@app.route(f'/{_COMMANDS_ROUTE}', methods=['POST'])
def run_command_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/commands
    command = request.json['command']
    execution_id = str(get_command_uuid())
    instance = _AUTOSCALING_GROUP.get_available_instance_for_execution(
        execution_id)
    if instance is None:
        response = jsonify(
            {'error': 'Couldn\'t get an instance, please retry later'})
        response.status_code = requests.codes.timeout
        return response
    # TODO: use private ip? (It's harder for testing)
    run_command(
        AutoScalingGroup.get_public_ip_of_instance(instance),
        command, execution_id)
    response = jsonify({'id': execution_id})
    response.status_code = requests.codes.accepted
    return response


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}',
           methods=['GET'])
def get_output_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs
    return _stream_binary_generator(
        get_logs_of_execution(
            get_ip_for_execution_id(execution_id), execution_id))


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stdout')
def get_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    # TODO(sergio): implement
    raise NotImplemented(execution_id)


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>/{_LOGS_SUBROUTE}/stderr')
def get_stderr_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    # TODO(sergio): implement
    raise NotImplemented(execution_id)


@app.route(f'/{_COMMANDS_ROUTE}/<execution_id>',
           methods=['DELETE'])
def delete_process(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/commands/some-id
    delete_container(get_ip_for_execution_id(execution_id),
                     execution_id)
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route('/snapshots', methods=['POST'])
def create_snapshot():
    # Test with
    # { echo '{"user": "bruce", "project": "mobile"}'; cat some_file.tar.bz2; }
    #     | http localhost:5000/snapshots
    # Create a timestamp in milliseconds
    timestamp = str(int(time.time() * 1000))
    # Read a string with a json object until a newline is found.
    # Using the utf-8 decoder from the codecs module fails as it's decoding
    # beyond the new line (even using readline(). Probably it does a read()
    # and decodes everything it gets, as it's not possible to push back to
    # the request stream). We don't use readline on a BufferedReader as the
    # the request.stream is a LimitedStream that doesn't support it.
    b = None
    json_bytes = []
    while b != b'\n':
        b = request.stream.read(1)
        if len(b) == 0:
            raise ValueError('Expected json at the beginning of request')
        json_bytes.append(b)
    metadata_str = str(b''.join(json_bytes), 'utf-8')
    metadata = json.loads(metadata_str)
    tag = f'{metadata["user"]}-{metadata["project"]}:{timestamp}'
    # Pass the rest of the stream to docker
    _DOCKER_CLIENT.images.build(
        fileobj=request.stream, custom_context=True, encoding='bz2', tag=tag)
    response = jsonify({'id': tag})
    response.status_code = requests.codes.ok
    return response


def get_command_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))


def run_command(worker_ip: str, command: str, execution_id: str):
    """
    Runs a command in a worker.

    Returns a unique id for the command execution, that can be passed to other
    entrypoints as to retrieve information about the execution

    :param worker_ip: IP to connect via ssh
    :param command: command to run with 'bash -c'
    :param execution_id: id of the execution of the command, used to name
           resources (like the docker container)
    """
    _check_ip(worker_ip)
    _check_execution_id(execution_id)
    # TODO(sergio): do not hardcode image
    # Intellij doesn't know about the encoding argument. All
    # suppresions in this function are related to that
    # (it thinks that the pipe outputs bytes)
    # noinspection PyArgumentList
    p = subprocess.Popen([
        'ssh', f'ubuntu@{worker_ip}',
        'docker', 'run', '-d', '--name', execution_id,
        '024444204267.dkr.ecr.eu-west-1.amazonaws.com/ml-pytorch',
        'bash', '-c', f'{shlex.quote(command)}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    stdout, stderr = p.communicate()

    # noinspection PyTypeChecker
    container_id = stdout.rstrip('\n')
    # noinspection PyTypeChecker
    if stderr != '' or p.returncode != 0 or \
            not check_is_container_id(container_id):
        raise ControllerException(
            f'Error running command\n'
            f'Exit code: [{p.returncode}]\n'
            f'Stdout is [{stdout}]\n'
            f'Stderr is [{stderr}]\n')
    _LOGGER.info(f'Container id is: {container_id}')


def get_ip_for_execution_id(execution_id):
    return AutoScalingGroup.get_public_ip_of_instance(
        _AUTOSCALING_GROUP.get_instance_from_execution_id(
            execution_id))


def check_is_container_id(container_id: str):
    if len(container_id) != 64:
        return False
    try:
        int(container_id, 16)
    except ValueError:
        return False
    return True


def _check_ip(worker_ip: str):
    try:
        socket.inet_aton(worker_ip)
    except OSError:
        raise ValueError(f'Invalid worker IP: [{worker_ip}]')


def _check_execution_id(execution_id: str):
    try:
        uuid.UUID(execution_id)
    except ValueError:
        raise ValueError(f'Invalid command id:[{execution_id}]')


def get_logs_of_execution(worker_ip: str, execution_id: str):
    p = None
    try:
        _check_ip(worker_ip)
        _check_execution_id(execution_id)
        p = subprocess.Popen(
            ['bash', '-c',
             f'ssh ubuntu@{worker_ip} ' +
             shlex.quote(f'docker logs {execution_id} -f 2>&1')],
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
            # Poll stderr to see if there's something (using peek might block
            # if there's nothing)
            stderr_to_read, _, _ = select.select(
                [p.stderr.fileno()], [], [], 0.1)
            if stderr_to_read:
                # Using peek: read might block if the process hasn't finished,
                # read1 requires an argument for the maximum size. If there's
                # actually something we won't keep reading, so using peek is
                # OK
                stderr = p.stderr.peek()
                # Check the length, if the process is already finished we
                # might be reading the empty bytes, and there was no error
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


def delete_container(worker_ip: str, execution_id: str):
    _check_ip(worker_ip)
    _check_execution_id(execution_id)
    subprocess.run(
        ['ssh',  f'ubuntu@{worker_ip}',
         f'docker stop {execution_id}'],
        stdout=None,
        stderr=None,
        check=True)
    subprocess.run(
        ['ssh', f'ubuntu@{worker_ip}',
         f'docker rm {execution_id}'],
        stdout=None,
        stderr=None,
        check=True)
    _AUTOSCALING_GROUP.execution_finished(execution_id)


def _stream_binary_generator(generator: Generator) -> Response:
    return Response(stream_with_context(generator),
                    mimetype='application/octet-stream')


class ControllerException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class InconsistentAwsResourceStateException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


app.run()
