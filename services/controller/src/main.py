import json
import logging
import random
import uuid
from typing import Any, Callable, Iterator, TypeVar, Union

import boto3
import docker
import requests
from flask import Flask, Response, jsonify, request, stream_with_context

from controller_config import config
from images import Images
from instances.aws import AwsAutoScalingGroup
from instances.instance_base import InstanceProvider
from instances.localhost import Localhost

T = TypeVar('T')

log = logging.getLogger('controller')
ecr_client = boto3.client('ecr')
docker_client = docker.APIClient(base_url=config.docker_host)
images = Images.from_config(config)

instance_provider: InstanceProvider
if config.run_commands_locally:
    instance_provider = Localhost.from_config(config)
else:
    instance_provider = AwsAutoScalingGroup.from_config(config)

app = Flask(__name__)


@app.route(f'/commands', methods=['POST'])
def run_command_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/commands
    command = request.json['command']
    snapshot_id = request.json['snapshot_id']
    execution_id = str(get_command_uuid())

    @_json_stream
    @stream_with_context
    def act() -> Iterator[dict]:
        yield {'id': execution_id}

        try:
            messages = instance_provider.acquire_instance(execution_id)
            for message in messages:
                yield {'status': message}
            instance = instance_provider.instance_for(execution_id)
            if instance is None:
                yield {
                    'error': 'Couldn\'t get an instance.',
                }
                return

            instance.run(command=command, snapshot_id=snapshot_id)
        except Exception as e:
            log.exception('Exception running command.')
            yield {'error': str(e)}

    response = Response(act(), mimetype='text/plain')
    response.status_code = requests.codes.accepted
    return response


@app.route(f'/commands/<execution_id>/logs',
           methods=['GET'])
def get_logs_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs()
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/commands/<execution_id>/logs/stdout')
def get_logs_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stdout
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs(stdout=True, stderr=False)
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/commands/<execution_id>/logs/stderr')
def get_logs_stderr_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/commands/some-id/logs/stderr
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs(stdout=False, stderr=True)
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/commands/<execution_id>',
           methods=['DELETE'])
def delete_process(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/commands/some-id
    instance_provider.release_instance(execution_id)
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route('/snapshots', methods=['POST'])
def create_snapshot():
    # Test with
    # { echo '{"user": "bruce", "project": "mobile"}'; cat some_file.tar.bz2; }
    #     | http localhost:5000/snapshots

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
    tag = Images.construct_tag(metadata_str)

    @stream_with_context
    @_handle_lazy_exceptions(formatter=_format_error)
    def act() -> Iterator[Union[bytes, str]]:
        # Pass the rest of the stream to `docker build`
        yield from images.build(request.stream, tag)
        instance_provider.push(tag)
        yield json.dumps({'id': tag})

    return Response(act(), mimetype='text/plain')


def get_command_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))


def _json_stream(f: Callable[[], Iterator[Any]]):
    def wrapped() -> Iterator[str]:
        return (json.dumps(message) + '\n' for message in f())

    return wrapped


def _handle_lazy_exceptions(formatter: Callable[[str], T]):
    def wrapper(f):
        def wrapped():
            # noinspection PyBroadException
            try:
                for value in f():
                    yield value
            except Exception as e:
                yield formatter(str(e) + '\n')
                log.exception('Exception in response generator')

        return wrapped

    return wrapper


def _format_error(message: str) -> bytes:
    return json.dumps({'error': message}).encode('utf-8')


app.run(host='0.0.0.0', port=config.port)
