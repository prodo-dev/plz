import hashlib
import json
import logging
import os
import random
import re
import tempfile
import threading
import uuid
from typing import Any, Callable, Iterator, TypeVar, Union

import boto3
import docker
import requests
from flask import Flask, Response, abort, jsonify, request, stream_with_context

from plz.controller.controller_config import config
from plz.controller.images import Images
from plz.controller.instances.aws import EC2InstanceGroup
from plz.controller.instances.instance_base import InstanceProvider
from plz.controller.instances.localhost import Localhost

READ_BUFFER_SIZE = 16384

T = TypeVar('T')

input_dir = os.path.join(config.data_dir, 'input')
temp_data_dir = os.path.join(config.data_dir, 'tmp')

log = logging.getLogger('controller')
ecr_client = boto3.client('ecr')
docker_client = docker.APIClient(base_url=config.docker_host)
images = Images.from_config(config)

instance_provider: InstanceProvider
if config.run_executions_locally:
    instance_provider = Localhost.from_config(config)
else:
    instance_provider = EC2InstanceGroup.from_config(config)

_user_last_execution_id_lock = threading.RLock()
_user_last_execution_id = dict()

app = Flask(__name__)


@app.before_request
def handle_chunked_input():
    """
    Sets the "wsgi.input_terminated" environment flag to tell Werkzeug to pass
    chunked requests as streams.
    The Gunicorn server should set the flag, but doesn't.
    """
    transfer_encoding = request.headers.get('Transfer-Encoding', None)
    if transfer_encoding == 'chunked':
        request.environ['wsgi.input_terminated'] = True


@app.route(f'/executions', methods=['POST'])
def run_execution_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/executions
    command = request.json['command']
    snapshot_id = request.json['snapshot_id']
    parameters = request.json['parameters']
    execution_spec = request.json['execution_spec']
    execution_id = str(get_execution_uuid())

    @_json_stream
    @stream_with_context
    def act() -> Iterator[dict]:
        yield {'id': execution_id}

        try:
            messages = instance_provider.acquire_instance(
                execution_id, execution_spec)
            for message in messages:
                yield {'status': message}
            instance = instance_provider.instance_for(execution_id)
            if instance is None:
                yield {
                    'error': 'Couldn\'t get an instance.',
                }
                return

            input_stream = prepare_input_stream(execution_spec)
            instance.run(
                command=command,
                snapshot_id=snapshot_id,
                parameters=parameters,
                input_stream=input_stream)
        except Exception as e:
            log.exception('Exception running command.')
            yield {'error': str(e)}

    response = Response(act(), mimetype='text/plain')
    response.status_code = requests.codes.accepted
    _set_user_last_execution_id(execution_spec['user'], execution_id)
    return response


@app.route('/executions/list', methods=['GET'])
def list_executions_entrypoint():
    # It's not protected, it's preceded by underscore as to avoid
    # name conflicts, see docs
    # noinspection PyProtectedMember
    as_dict = [info._asdict()
               for info in instance_provider.get_executions()]
    response = Response(
        json.dumps({'executions': as_dict}),
        mimetype='application/json')
    response.status_code = requests.codes.ok
    return response


@app.route('/executions/tidy', methods=['POST'])
def tidy_entry_point():
    instance_provider.tidy_up()
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route(f'/executions/<execution_id>/status',
           methods=['GET'])
def get_status_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/status
    instance = instance_provider.instance_for(execution_id)
    state = instance.get_container_state()
    if state.running:
        return jsonify({
            'running': True,
        })
    else:
        return jsonify({
            'running': False,
            'success': state.success,
            'code': state.exit_code,
        })


@app.route(f'/executions/<execution_id>/logs',
           methods=['GET'])
def get_logs_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/logs
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs()
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/logs/stdout')
def get_logs_stdout_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/logs/stdout
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs(stdout=True, stderr=False)
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/logs/stderr')
def get_logs_stderr_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/logs/stderr
    instance = instance_provider.instance_for(execution_id)
    response = instance.logs(stdout=False, stderr=True)
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/output/files')
def get_output_files_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/output | tar x -C /tmp/plz-output
    instance = instance_provider.instance_for(execution_id)
    response = instance.output_files_tarball()
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>',
           methods=['DELETE'])
def delete_process(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/executions/some-id
    instance_provider.release_instance(execution_id)
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route(f'/executions/<execution_id>/stop', methods=['POST'])
def stop_execution_entrypoint(execution_id: str):
    instance_provider.stop_execution(execution_id)
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route('/snapshots', methods=['POST'])
def create_snapshot():
    metadata_str = request.stream.readline().decode('utf-8')
    tag = Images.construct_tag(metadata_str)

    @stream_with_context
    @_handle_lazy_exceptions(formatter=_format_error)
    def act() -> Iterator[Union[bytes, str]]:
        # Pass the rest of the stream to `docker build`
        yield from images.build(request.stream, tag)
        instance_provider.push(tag)
        yield json.dumps({'id': tag})

    return Response(act(), mimetype='text/plain')


@app.route('/data/input/<input_id>', methods=['HEAD'])
def check_input_data(input_id: str):
    if os.path.exists(input_file(input_id)):
        return jsonify({
            'id': input_id,
        })
    else:
        abort(404)


@app.route('/data/input/<expected_input_id>', methods=['PUT'])
def publish_input_data(expected_input_id: str):
    input_file_path = input_file(expected_input_id)
    if os.path.exists(input_file_path):
        request.stream.close()
        return jsonify({
            'id': expected_input_id,
        })

    file_hash = hashlib.sha256()
    fd, temp_file_path = tempfile.mkstemp(dir=temp_data_dir)
    try:
        with os.fdopen(fd, 'wb') as f:
            while True:
                data = request.stream.read(READ_BUFFER_SIZE)
                if not data:
                    break
                f.write(data)
                file_hash.update(data)

        input_id = file_hash.hexdigest()
        if input_id != expected_input_id:
            abort(requests.codes.bad_request, 'The input ID was incorrect.')

        os.rename(temp_file_path, input_file_path)
        return jsonify({
            'id': input_id,
        })
    except Exception:
        os.remove(temp_file_path)
        raise


@app.route('/data/input/<input_id>', methods=['DELETE'])
def delete_input_data(input_id: str):
    try:
        os.remove(input_file(input_id))
    except FileNotFoundError:
        pass


@app.route(f'/users/<user>/last_execution_id')
def last_execution_id_entrypoint(user: str):
    last_execution_id = _get_user_last_execution_id(user)
    response_object = {}
    if last_execution_id is not None:
        response_object['execution_id'] = last_execution_id
    response = jsonify(response_object)
    response.status_code = requests.codes.ok
    return response


def input_file(input_id: str):
    if not re.match(r'^\w{64}$', input_id):
        abort(requests.codes.bad_request, 'Invalid input ID.')
    input_file_path = os.path.join(input_dir, input_id)
    return input_file_path


def prepare_input_stream(execution_spec: dict):
    input_id = execution_spec.get('input_id')
    if not input_id:
        return None
    try:
        input_file_path = input_file(input_id)
        return open(input_file_path, 'rb')
    except FileNotFoundError:
        abort(requests.codes.bad_request, 'Invalid input ID.')


def get_execution_uuid() -> str:
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


def _set_user_last_execution_id(user: str, execution_id: str):
    _user_last_execution_id_lock.acquire()
    _user_last_execution_id[user] = execution_id
    _user_last_execution_id_lock.release()


def _get_user_last_execution_id(user: str):
    last_execution_id = None
    _user_last_execution_id_lock.acquire()
    if user in _user_last_execution_id:
        last_execution_id = _user_last_execution_id[user]
    _user_last_execution_id_lock.release()
    return last_execution_id


if __name__ == '__main__':
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(temp_data_dir, exist_ok=True)
    app.run(host='0.0.0.0', port=config.port)
