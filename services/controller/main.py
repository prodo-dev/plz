# coding=utf-8

import base64
import json
import logging
import random
import select
import shlex
import socket
import subprocess
import time
import uuid
from typing import Callable, Iterator, Optional, TypeVar, Union

import boto3
import docker
import requests
from flask import Flask, Response, jsonify, request, stream_with_context

from AutoScalingGroup import AutoScalingGroup
from controller_config import config

T = TypeVar('T')

log = logging.getLogger('controller')
ecr_client = boto3.client('ecr')
docker_client = docker.APIClient(base_url=config.docker_host)
autoscaling_group = AutoScalingGroup(config.aws_autoscaling_group)

app = Flask(__name__)


@app.route(f'/commands', methods=['POST'])
def run_command_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/commands
    command = request.json['command']
    snapshot = request.json['snapshot']
    execution_id = str(get_command_uuid())

    def act() -> Iterator[dict]:
        yield {'id': execution_id}

        if config.run_commands_locally:
            worker_ip = None
        else:
            instance = None
            messages = autoscaling_group.get_available_instance_for_execution(
                execution_id)
            for message in messages:
                if type(message) == str:
                    yield {'status': message}
                else:
                    instance = message
            if instance is None:
                yield {
                    'error': 'Couldn\'t get an instance, please retry later',
                }
                response.status_code = requests.codes.timeout
                return response
            # TODO: use private ip? (It's harder for testing)
            worker_ip = AutoScalingGroup.get_public_ip_of_instance(instance)

        run_command(worker_ip, command, snapshot, execution_id)

    response = _binary_stream(json.dumps(message) + '\n' for message in act())
    response.status_code = requests.codes.accepted
    return response


@app.route(f'/commands/<execution_id>/logs',
           methods=['GET'])
def get_output_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs
    response = get_logs_of_execution(
        get_ip_for_execution_id(execution_id), execution_id)
    return _binary_stream(response)


@app.route(f'/commands/<execution_id>/logs/stdout')
def get_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    # TODO(sergio): implement
    raise NotImplemented(execution_id)


@app.route(f'/commands/<execution_id>/logs/stderr')
def get_stderr_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    # TODO(sergio): implement
    raise NotImplemented(execution_id)


@app.route(f'/commands/<execution_id>',
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

    # Authenticate with AWS ECR
    ecr_auth_data = ecr_client.get_authorization_token()['authorizationData']
    ecr_encoded_token = ecr_auth_data[0]['authorizationToken']
    ecr_token = base64.b64decode(ecr_encoded_token).decode('utf-8')
    ecr_user, ecr_password = ecr_token.split(':')

    # Pass the rest of the stream to docker
    docker_client.login(ecr_user, ecr_password, registry=config.aws_project)
    response = docker_client.build(
        fileobj=request.stream,
        custom_context=True,
        encoding='bz2',
        rm=True,
        tag=tag)
    return _binary_stream(_handle_lazy_exceptions(
        response,
        formatter=lambda message: json.dumps({'error': message})
            .encode('utf-8')))


def get_command_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))


def maybe_prepend_ssh(subprocess_token_list: [str], worker_ip):
    _check_ip(worker_ip, allow_none=config.run_commands_locally)
    if config.run_commands_locally:
        return subprocess_token_list
    return \
        ['ssh',
         '-o', 'LogLevel=ERROR',
         '-o', 'StrictHostKeyChecking=no',
         '-o', 'UserKnownHostsFile=/dev/null',
         f'ubuntu@{worker_ip}'] \
        + subprocess_token_list


def run_command(worker_ip: str, command: str, snapshot: str,
                execution_id: str):
    """
    Runs a command in a worker.

    Returns a unique id for the command execution, that can be passed to other
    entrypoints as to retrieve information about the execution

    :param worker_ip: IP to connect via ssh
    :param command: command to run with 'bash -c'
    :param snapshot: id of the snapshot to run the command
    :param execution_id: id of the execution of the command, used to name
           resources (like the docker container)
    """
    _check_execution_id(execution_id)
    # TODO(sergio): check the snapshot

    subprocess_token_list = \
        ['docker', 'run', '-d', '--name', execution_id, snapshot,
         'bash', '-c', command]
    # Intellij doesn't know about the encoding argument. All
    # suppresions in this function are related to that
    # (it thinks that the pipe outputs bytes)
    # noinspection PyArgumentList
    p = subprocess.Popen(
        maybe_prepend_ssh(subprocess_token_list, worker_ip),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    stdout, stderr = p.communicate()

    # noinspection PyTypeChecker
    container_id = stdout.rstrip('\n')
    # noinspection PyTypeChecker
    if stderr != '' or p.returncode != 0 or \
            not is_container_id(container_id):
        raise ControllerException(
            f'Error running command\n'
            f'Exit code: [{p.returncode}]\n'
            f'Stdout is [{stdout}]\n'
            f'Stderr is [{stderr}]\n')
    log.info(f'Container id is: {container_id}')


def get_ip_for_execution_id(execution_id):
    if config.run_commands_locally:
        return None
    else:
        return AutoScalingGroup.get_public_ip_of_instance(
            autoscaling_group.get_instance_from_execution_id(execution_id))


def is_container_id(container_id: str):
    if len(container_id) != 64:
        return False
    try:
        int(container_id, 16)
    except ValueError:
        return False
    return True


def _check_ip(ip: Optional[str], allow_none=False):
    """Throws an exception in case of an invalid IP"""
    if ip is None:
        if allow_none:
            return
        else:
            raise ValueError('Expected an IP, got None')
    try:
        socket.inet_aton(ip)
    except OSError:
        raise ValueError(f'Invalid worker IP: [{ip}]')


def _check_execution_id(execution_id: str):
    try:
        uuid.UUID(execution_id)
    except ValueError:
        raise ValueError(f'Invalid command id:[{execution_id}]')


def get_logs_of_execution(worker_ip: str, execution_id: str):
    p = None
    try:
        _check_execution_id(execution_id)
        # Make the redirection happen in the worker side
        docker_command = f'docker logs {execution_id} -f 2>&1'
        if config.run_commands_locally:
            # Need bash -c if running locally
            subprocess_token_list = ['bash', '-c', docker_command]
        else:
            subprocess_token_list = [docker_command]
        subprocess_token_list = \
            maybe_prepend_ssh(subprocess_token_list, worker_ip)
        p = subprocess.Popen(
            maybe_prepend_ssh(subprocess_token_list, worker_ip),
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
            yield out
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
    _check_execution_id(execution_id)
    execution_id = shlex.quote(execution_id)
    subprocess.run(
        maybe_prepend_ssh(['docker', 'stop', execution_id], worker_ip),
        stdout=None,
        stderr=None,
        check=True)
    subprocess.run(
        maybe_prepend_ssh(['docker', 'rm', execution_id], worker_ip),
        stdout=None,
        stderr=None,
        check=True)
    if worker_ip is not None:
        autoscaling_group.execution_finished(execution_id)


def _binary_stream(generator: Iterator[Union[bytes, str]],
                   mimetype: str = 'application/octet-stream') -> Response:
    return Response(
        stream_with_context(
            value if type(value) == bytes else value.encode('utf8')
            for value
            in generator),
        mimetype=mimetype)


def _handle_lazy_exceptions(generator: Iterator[T],
                            formatter: Callable[[str], T]) -> Iterator[T]:
    # noinspection PyBroadException
    try:
        for value in generator:
            yield value
    except Exception as e:
        yield formatter(str(e) + '\n')
        log.exception('Exception in response generator')


class ControllerException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


class InconsistentAwsResourceStateException(Exception):
    def __init__(self, msg):
        super().__init__(msg)


app.run(host='0.0.0.0', port=config.port)
