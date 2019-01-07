import json
import logging
import os
import sys
from distutils.util import strtobool
from typing import Any, Callable, Iterator, Optional, TypeVar, Union

import requests
from flask import Flask, Response, abort, jsonify, request, stream_with_context

from plz.controller import configuration
from plz.controller.api.exceptions import AbortedExecutionException, \
    InstanceNotRunningException, JSONResponseException, \
    ResponseHandledException, WorkerUnreachableException
from plz.controller.api.types import InputMetadata, JSONString
from plz.controller.arbitrary_object_json_encoder import \
    ArbitraryObjectJSONEncoder
from plz.controller.controller_impl import ControllerImpl

T = TypeVar('T')
ResponseGenerator = Iterator[Union[bytes, str]]
ResponseGeneratorFunction = Callable[[], ResponseGenerator]

config = configuration.load()
port = config.get_int('port', 8080)


def _setup_logging():
    # Setup handler for the root logger (there's no default one in our context,
    # probably because of gunicorn) so that we can turn on loggers for other
    # modules, like docker
    root_logger = logging.getLogger()
    root_logger_handler = logging.StreamHandler(stream=sys.stderr)
    root_logger_handler.setFormatter(logging.Formatter(
        '%(asctime)s ' + logging.BASIC_FORMAT))
    root_logger.addHandler(root_logger_handler)
    # Set log level for the controller
    if 'log_level' in config:
        log_level = config['log_level']
        print(f'Setting log level to: {log_level}',
              file=sys.stderr, flush=True)
        controller_logger = logging.getLogger(
            '.'.join(__name__.split('.')[:-1]))
        controller_logger.setLevel(log_level)


def _get_build_timestamp() -> int:
    dir_of_this_script = os.path.dirname(os.path.abspath(__file__))
    build_timestamp_filename = f'{dir_of_this_script}/BUILD_TIMESTAMP'
    if not os.path.exists(build_timestamp_filename):
        # Not present in development
        return 0
    with open(f'{dir_of_this_script}/BUILD_TIMESTAMP', 'r') as f:
        build_timestamp = f.read()
    if build_timestamp == '':
        # Non-deployment build
        return 0
    return int(build_timestamp)


app = Flask(__name__)
app.json_encoder = ArbitraryObjectJSONEncoder

_setup_logging()
log = logging.getLogger(__name__)

_build_timestamp = _get_build_timestamp()
log.info(f'Build timestamp: {_build_timestamp}')

controller = ControllerImpl(config, log)


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


@app.errorhandler(ResponseHandledException)
def handle_exception(exception: ResponseHandledException):
    if isinstance(exception, WorkerUnreachableException):
        exception = maybe_add_forensics(exception)
    return jsonify(exception_type=type(exception).__name__,
                   **{k: v for k, v in exception.__dict__.items()
                      if k != 'response_code'}), \
        exception.response_code


def maybe_add_forensics(exception: WorkerUnreachableException) \
        -> ResponseHandledException:
    forensics = controller.instance_provider.get_forensics(
        exception.execution_id)
    spot_state = forensics.get(
        'SpotInstanceRequest', {}).get('State', None)
    # We know better now
    if spot_state not in {'active', 'open', None}:
        return AbortedExecutionException(forensics)
    instance_state = forensics.get('InstanceState', None)
    if instance_state not in {'running', None}:
        return InstanceNotRunningException(forensics)
    exception.forensics = forensics
    return exception


@app.route('/ping', methods=['GET'])
def ping_entrypoint():
    # We are not calling a server, so the timeout is not used
    return jsonify(
        controller.ping(
            ping_timeout=0,
            build_timestamp=_build_timestamp))


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
    start_metadata = request.json['start_metadata']
    instance_market_spec = request.json.get('instance_market_spec')
    parallel_indices_range = request.json.get('parallel_indices_range')
    indices_per_execution = request.json.get('indices_per_execution')

    @_json_stream
    @stream_with_context
    def act() -> Iterator[dict]:
        yield from controller.run_execution(
            command, snapshot_id, parameters, instance_market_spec,
            execution_spec, start_metadata, parallel_indices_range,
            indices_per_execution)
    return Response(
        act(), mimetype='text/plain', status=requests.codes.accepted)


@app.route(f'/executions/rerun', methods=['POST'])
def rerun_execution_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/executions
    user = request.json['user']
    project = request.json['project']
    instance_max_uptime_in_minutes = \
        request.json['instance_max_uptime_in_minutes']
    previous_execution_id = request.json['execution_id']
    # Using market spec from the request. Results should be independent of
    # the market and bid price. If a user is trying to run cheaper at the
    # moment, there'll be surprises if we do not honor the current
    # configuration
    instance_market_spec = request.json['instance_market_spec']
    override_parameters = request.json['override_parameters']

    @_json_stream
    @stream_with_context
    def act() -> Iterator[dict]:
        yield from controller.rerun_execution(
            user, project,
            instance_max_uptime_in_minutes,
            override_parameters,
            previous_execution_id, instance_market_spec)
    return Response(
        act(), mimetype='text/plain', status=requests.codes.accepted)


@app.route('/executions/list', methods=['GET'])
def list_executions_entrypoint():
    user: str = request.args.get('user', type=str)
    list_for_all_users: bool = request.args.get(
        'list_for_all_users', type=strtobool, default=False)

    log.debug(f'Listing for: {user} {list_for_all_users}')

    return Response(
        json.dumps({
            'executions': controller.list_executions(user, list_for_all_users)
        }),
        mimetype='application/json',
        status=requests.codes.ok)


@app.route('/executions/harvest', methods=['POST'])
def harvest_entry_point():
    controller.harvest()
    return jsonify({}), requests.codes.no_content


@app.route(f'/executions/<execution_id>/status',
           methods=['GET'])
def get_status_entrypoint(execution_id):
    return jsonify(controller.get_status(execution_id))


@app.route(f'/executions/<execution_id>/logs',
           methods=['GET'])
def get_logs_entrypoint(execution_id):
    since: Optional[int] = request.args.get(
        'since', default=None, type=int)
    return Response(controller.get_logs(execution_id, since=since),
                    mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/output/files')
def get_output_files_entrypoint(execution_id):
    path: Optional[str] = request.args.get('path', default=None, type=str)
    index: Optional[int] = request.args.get('index', default=None, type=int)
    return Response(controller.get_output_files(execution_id, path, index),
                    mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/measures', methods=['GET'])
def get_measures(execution_id):
    summary: bool = request.args.get(
        'summary', default=False, type=strtobool)
    index: Optional[int] = request.args.get('index', default=None, type=int)
    return Response(
        stream_with_context(controller.get_measures(
            execution_id, summary, index)),
        mimetype='text/plain')


@app.route(f'/executions/<execution_id>', methods=['DELETE'])
def delete_execution(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/executions/some-id
    fail_if_running: bool = request.args.get(
        'fail_if_running', default=False, type=strtobool)
    fail_if_deleted: bool = request.args.get(
        'fail_if_deleted', default=False, type=strtobool)
    controller.delete_execution(
        execution_id, fail_if_running=fail_if_running,
        fail_if_deleted=fail_if_deleted)
    return jsonify({}), requests.codes.no_content


@app.route(f'/executions/<user>/<project>/history', methods=['GET'])
def history_entrypoint(user, project):
    return Response(
        stream_with_context(controller.get_history(user, project)),
        mimetype='text/plain')


@app.route('/snapshots', methods=['POST'])
def create_snapshot():
    image_metadata = json.loads(request.stream.readline().decode('utf-8'))

    @stream_with_context
    @_handle_lazy_exceptions
    def act() -> Iterator[JSONString]:
        # Pass the rest of the stream to `docker build`
        yield from controller.create_snapshot(image_metadata, request.stream)

    return Response(act(), mimetype='text/plain')


@app.route('/data/input/<input_id>', methods=['PUT'])
def put_input_entrypoint(input_id: str):
    input_metadata = _get_input_metadata_from_request()
    controller.put_input(input_id, input_metadata, request.stream)
    return jsonify({'id': input_id})


@app.route('/data/input/<input_id>', methods=['HEAD'])
def check_input_data_entrypoint(input_id: str):
    is_present = controller.check_input_data(
        input_id, _get_input_metadata_from_request())
    if is_present:
        return jsonify({'id': input_id})
    else:
        abort(requests.codes.not_found)


@app.route('/data/input/id', methods=['GET'])
def get_input_id_entrypoint():
    input_metadata = _get_input_metadata_from_request()
    return jsonify({'id': controller.get_input_id_or_none(input_metadata)})


@app.route('/data/input/<input_id>', methods=['DELETE'])
def delete_input_data(input_id: str):
    controller.delete_input_data(input_id)


@app.route(f'/users/<user>/last_execution_id')
def last_execution_id_entrypoint(user: str):
    last_execution_id = controller.get_user_last_execution_id(user)
    response_object = {}
    if last_execution_id is not None:
        response_object['execution_id'] = last_execution_id
    return jsonify(response_object)


@app.route(f'/instances/kill', methods=['POST'])
def kill_instances_entrypoint():
    # TODO: make the entrypoint receive the instance ids instead of
    # implementing this logic. The CLI converts the all_of_them_plz boolean to
    # a list of instances, then the proxy on the CLI side reconverts that
    # to all_of_them_plz as to fit the entrypoint, which is bizarre
    all_of_them_plz: bool = request.json['all_of_them_plz']
    if all_of_them_plz:
        instance_ids = None
    else:
        instance_ids: [str] = request.json['instance_ids']
    force_if_not_idle = request.json['force_if_not_idle']

    were_there_instances_to_kill = controller.kill_instances(
        instance_ids=instance_ids, force_if_not_idle=force_if_not_idle)

    response_dict = {
        'were_there_instances_to_kill': were_there_instances_to_kill}

    return jsonify(response_dict)


@app.route(f'/executions/describe/<execution_id>', methods=['GET'])
def describe_execution_entrypoint(execution_id: str):
    return jsonify(controller.describe_execution_entrypoint(execution_id))


@app.route('/executions/composition/<execution_id>', methods=['GET'])
def get_execution_composition_entrypoint(execution_id: str):
    return jsonify(controller.get_execution_composition(execution_id))


def _json_stream(f: Callable[[], Iterator[Any]]):
    def wrapped() -> Iterator[str]:
        return (json.dumps(message) + '\n' for message in f())

    return wrapped


def _handle_lazy_exceptions(f: ResponseGeneratorFunction) \
        -> ResponseGeneratorFunction:
    def wrapped() -> ResponseGenerator:
        # noinspection PyBroadException
        try:
            for value in f():
                yield value
        except JSONResponseException as e:
            yield e.args[0]
            log.exception('Exception in response generator')
        except Exception as e:
            message = str(e) + '\n'
            yield json.dumps({'error': message})
            log.exception('Exception in response generator')

    return wrapped


def _get_input_metadata_from_request() -> InputMetadata:
    metadata: InputMetadata = InputMetadata()
    metadata.user = request.args.get('user', default=None, type=str)
    metadata.project = request.args.get(
        'project', default=None, type=str)
    metadata.path = request.args.get(
        'path', default=None, type=str)
    metadata.timestamp_millis = request.args.get(
        'timestamp_millis', default=None, type=str)
    return metadata


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
