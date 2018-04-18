import hashlib
import json
import logging
import os
import random
import re
import sys
import tempfile
import uuid
from typing import Any, Callable, Iterator, Optional, TypeVar, Union

import flask
import requests
from flask import Flask, Response, abort, jsonify, request, stream_with_context
from redis import StrictRedis

from plz.controller import configuration
from plz.controller.configuration import Dependencies
from plz.controller.images import Images
from plz.controller.instances.instance_base import Instance, \
    InstanceProvider, InstanceStatusFailure, InstanceStatusSuccess
from plz.controller.results import ResultsStorage

READ_BUFFER_SIZE = 16384

T = TypeVar('T')

config = configuration.load()
port = config.get_int('port', 8080)
data_dir = config['data_dir']
input_dir = os.path.join(data_dir, 'input')
temp_data_dir = os.path.join(data_dir, 'tmp')
dependencies: Dependencies = configuration.dependencies_from_config(config)
images: Images = dependencies.images
instance_provider: InstanceProvider = dependencies.instance_provider
results_storage: ResultsStorage = dependencies.results_storage
redis: StrictRedis = dependencies.redis

os.makedirs(input_dir, exist_ok=True)
os.makedirs(temp_data_dir, exist_ok=True)


class ArbitraryObjectJSONEncoder(flask.json.JSONEncoder):
    """
    This encoder tries very hard to encode any kind of object. It uses the
     object's ``__dict__`` property if the object itself is not encodable.
    """
    def default(self, o):
        try:
            return super().default(o)
        except TypeError:
            return o.__dict__


def _setup_logging():
    # Setup handler for the root logger (there's no default one in our context,
    # probably because of gunicorn) so that we can turn on loggers for other
    # modules, like docker
    root_logger = logging.getLogger()
    root_logger_handler = logging.StreamHandler(stream=sys.stderr)
    root_logger_handler.setFormatter(logging.Formatter(
        '%(asctime)s ' + logging.BASIC_FORMAT))
    root_logger.addHandler(root_logger_handler)
    # Set logger level for the controller
    if 'log_level' in config:
        log_level = config['log_level']
        print(f'Setting log level to: {log_level}',
              file=sys.stderr, flush=True)
        controller_logger = logging.getLogger(
            '.'.join(__name__.split('.')[:-1]))
        controller_logger.setLevel(log_level)


_setup_logging()
log = logging.getLogger(__name__)

app = Flask(__name__)
app.json_encoder = ArbitraryObjectJSONEncoder


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


@app.route('/', methods=['GET'])
def root():
    return jsonify({})


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
            acquisition_statuses = instance_provider.acquire_instance(
                    execution_id, execution_spec)
            instance: Optional[Instance] = None
            for status in acquisition_statuses:
                if 'message' in status:
                    yield {'status': status['message']}
                if 'instance' in status:
                    instance = status['instance']
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
                input_stream=input_stream,
                docker_runtime=execution_spec.get('docker_runtime', None))
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


@app.route('/executions/harvest', methods=['POST'])
def harvest_entry_point():
    instance_provider.harvest()
    response = jsonify({})
    response.status_code = requests.codes.no_content
    return response


@app.route(f'/executions/<execution_id>/status',
           methods=['GET'])
def get_status_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/status
    with results_storage.get(execution_id) as results:
        if results:
            status = results.status()
            if status == 0:
                return jsonify(InstanceStatusSuccess())
            else:
                return jsonify(InstanceStatusFailure(status))

    instance = instance_provider.instance_for(execution_id)
    return jsonify(instance.status())


@app.route(f'/executions/<execution_id>/logs',
           methods=['GET'])
def get_logs_entrypoint(execution_id):
    # Test with:
    # curl localhost:5000/executions/some-id/logs
    since: Optional[int] = request.args.get(
        'since', default=None, type=int)
    with results_storage.get(execution_id) as results:
        if results:
            # Use `since` parameter for logs of finished jobs
            response = results.logs()
            return Response(response, mimetype='application/octet-stream')

    instance = instance_provider.instance_for(execution_id)
    response = instance.logs(since=since)
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/output/files')
def get_output_files_entrypoint(execution_id):
    with results_storage.get(execution_id) as results:
        if results:
            response = results.output_tarball()
            return Response(response, mimetype='application/octet-stream')

    # Test with:
    # curl localhost:5000/executions/some-id/output | tar x -C /tmp/plz-output
    instance = instance_provider.instance_for(execution_id)
    response = instance.output_files_tarball()
    return Response(response, mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>',
           methods=['DELETE'])
def delete_execution(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/executions/some-id
    fail_if_running: bool = request.args.get(
        'fail_if_running', default=False, type=bool)
    response = jsonify({})
    instance = instance_provider.instance_for(execution_id)
    if fail_if_running and instance.get_execution_info().running:
        response.status_code = requests.codes.conflict
        return response
    instance_provider.release_instance(execution_id, fail_if_not_found=False)
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


def _set_user_last_execution_id(user: str, execution_id: str) -> None:
    redis.set(f'key:{__name__}#user_last_execution_id:{user}',
              execution_id)


def _get_user_last_execution_id(user: str) -> Optional[str]:
    execution_id_bytes = redis.get(
        f'key:{__name__}#user_last_execution_id:{user}')
    if execution_id_bytes:
        return str(execution_id_bytes, encoding='utf-8')
    else:
        return None


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
