import json
import logging
import os
import random
import sys
import uuid
from distutils.util import strtobool
from typing import Any, Callable, Iterator, Optional, TypeVar, Union

import requests
from flask import Flask, Response, abort, jsonify, request, stream_with_context
from redis import StrictRedis

from plz.controller import configuration
from plz.controller.arbitrary_object_json_encoder import \
    ArbitraryObjectJSONEncoder
from plz.controller.configuration import Dependencies
from plz.controller.db_storage import DBStorage
from plz.controller.exceptions import AbortedExecutionException, \
    JSONResponseException, ResponseHandledException, WorkerUnreachableException
from plz.controller.execution import ExecutionNotFoundException, Executions
from plz.controller.images import Images
from plz.controller.input_data import IncorrectInputID, \
    InputDataConfiguration, InputMetadata
from plz.controller.instances.instance_base import Instance, \
    InstanceNotRunningException, InstanceProvider, \
    InstanceStillRunningException, NoInstancesFound, \
    ProviderKillingInstancesException
from plz.controller.results import ResultsStorage

T = TypeVar('T')
ResponseGenerator = Iterator[Union[bytes, str]]
ResponseGeneratorFunction = Callable[[], ResponseGenerator]

config = configuration.load()
port = config.get_int('port', 8080)
data_dir = config['data_dir']
dependencies: Dependencies = configuration.dependencies_from_config(config)
images: Images = dependencies.images
instance_provider: InstanceProvider = dependencies.instance_provider
results_storage: ResultsStorage = dependencies.results_storage
db_storage: DBStorage = dependencies.db_storage
redis: StrictRedis = dependencies.redis
executions: Executions = Executions(results_storage, instance_provider)

input_dir = os.path.join(data_dir, 'input')
temp_data_dir = os.path.join(data_dir, 'tmp')
os.makedirs(input_dir, exist_ok=True)
os.makedirs(temp_data_dir, exist_ok=True)
input_data_configuration = InputDataConfiguration(
    redis, input_dir=input_dir, temp_data_dir=temp_data_dir)


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
    forensics = instance_provider.get_forensics(exception.execution_id)
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
    # This is plz, and we're up and running
    return jsonify({'plz': 'pong'})


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
    instance_market_spec = request.json.get(
        'instance_market_spec',
        # TODO: delete this once people update their CLI
        {
            'instance_market_type': 'spot',
            'max_bid_price_in_dollars_per_hour': 3,
            'instance_max_idle_time_in_minutes': 30
        })
    return run_execution(command, snapshot_id, parameters,
                         instance_market_spec, execution_spec,
                         start_metadata)


@app.route(f'/executions/rerun', methods=['POST'])
def rerun_execution_entrypoint():
    # Test with:
    # curl -X POST -d '{"command": "ls /" }'
    #    -H 'Content-Type: application/json' localhost:5000/executions
    user = request.json['user']
    project = request.json['project']
    previous_execution_id = request.json['execution_id']
    start_metadata = db_storage.retrieve_start_metadata(previous_execution_id)

    command = start_metadata['command']
    snapshot_id = start_metadata['snapshot_id']
    parameters = start_metadata['parameters']
    # Using market spec from the request. Results should be independent of the
    # market and bid price. If a user is trying to run cheaper at the moment,
    # there'll be surprises if we do not to honor the current configuration
    instance_market_spec = request.json['instance_market_spec']
    execution_spec = start_metadata['execution_spec']
    execution_spec['user'] = user
    execution_spec['project'] = project
    return run_execution(command, snapshot_id, parameters,
                         instance_market_spec, execution_spec,
                         start_metadata, previous_execution_id)


def run_execution(command: [str], snapshot_id: str, parameters: dict,
                  instance_market_spec: dict, execution_spec: dict,
                  start_metadata: dict,
                  previous_execution_id: Optional[str] = None):
    execution_id = str(get_execution_uuid())
    start_metadata['command'] = command
    start_metadata['snapshot_id'] = snapshot_id
    start_metadata['parameters'] = parameters
    start_metadata['instance_market_spec'] = instance_market_spec
    start_metadata['execution_spec'] = {k: v for k, v in execution_spec.items()
                                        if k not in {'user', 'project'}}
    start_metadata['user'] = execution_spec['user']
    start_metadata['project'] = execution_spec['project']
    start_metadata['previous_execution_id'] = previous_execution_id
    db_storage.store_start_metadata(execution_id, start_metadata)

    @_json_stream
    @stream_with_context
    def act() -> Iterator[dict]:
        yield {'id': execution_id}

        try:
            input_stream = input_data_configuration.prepare_input_stream(
                execution_spec)
            startup_statuses = instance_provider.run_in_instance(
                execution_id, command, snapshot_id, parameters, input_stream,
                instance_market_spec, execution_spec)
            instance: Optional[Instance] = None
            for status in startup_statuses:
                if 'message' in status:
                    yield {'status': status['message']}
                if 'instance' in status:
                    instance = status['instance']
            if instance is None:
                yield {
                    'error': 'Couldn\'t get an instance.',
                }
                return
        except IncorrectInputID:
            abort(requests.codes.bad_request, 'Invalid input ID.')
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
    return jsonify(executions.get(execution_id).get_status())


@app.route(f'/executions/<execution_id>/logs',
           methods=['GET'])
def get_logs_entrypoint(execution_id):
    since: Optional[int] = request.args.get(
        'since', default=None, type=int)
    return Response(executions.get(execution_id).get_logs(since=since),
                    mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/output/files')
def get_output_files_entrypoint(execution_id):
    return Response(executions.get(execution_id).get_output_files_tarball(),
                    mimetype='application/octet-stream')


@app.route(f'/executions/<execution_id>/measures', methods=['GET'])
def get_measures(execution_id):
    summary: bool = request.args.get(
        'summary', default=False, type=strtobool)

    measures = executions.get(execution_id).get_measures()
    if summary:
        measures_to_return = measures.get('summary', {})
    else:
        measures_to_return = measures
    if measures_to_return == {}:
        return Response('', status=requests.codes.no_content,
                        mimetype='text/plain')
    # We return text that happens to be json, as we want the cli to show it
    # indented properly and we don't want an additional conversion round
    # json <-> str.
    # In the future we can have another entrypoint or a parameter
    # to return the json if we use it programmatically in the CLI.
    str_response = json.dumps(measures_to_return, indent=2) + '\n'

    @stream_with_context
    def act():
        for l in str_response.splitlines(keepends=True):
            yield l
    return Response(act(), mimetype='text/plain')


@app.route(f'/executions/<execution_id>', methods=['DELETE'])
def delete_execution(execution_id):
    # Test with:
    # curl -XDELETE localhost:5000/executions/some-id
    fail_if_running: bool = request.args.get(
        'fail_if_running', default=False, type=strtobool)
    fail_if_deleted: bool = request.args.get(
        'fail_if_deleted', default=False, type=strtobool)
    response = jsonify({})
    status = executions.get(execution_id).get_status()
    if fail_if_running and status.running:
        raise InstanceStillRunningException(execution_id=execution_id)
    instance = instance_provider.instance_for(execution_id)
    if fail_if_deleted and instance is None:
        response.status_code = requests.codes.expectation_failed
        return response
    instance_provider.release_instance(execution_id, fail_if_not_found=False)
    response.status_code = requests.codes.no_content
    return response


@app.route(f'/executions/<user>/<project>/history', methods=['GET'])
def history_entrypoint(user, project):
    execution_ids = db_storage.retrieve_finished_execution_ids(user, project)

    @stream_with_context
    def act():
        yield '{\n'
        first = True
        for execution_id in execution_ids:
            if not first:
                yield ',\n'
            first = False
            yield f'"{execution_id}": ' \
                  f'{executions.get(execution_id).get_metadata()}'
        yield '\n}\n'

    response = Response(act(), mimetype='text/plain')
    response.status_code = requests.codes.ok
    return response


@app.route('/snapshots', methods=['POST'])
def create_snapshot():
    metadata_str = request.stream.readline().decode('utf-8')
    tag = Images.construct_tag(metadata_str)

    @stream_with_context
    @_handle_lazy_exceptions
    def act() -> Iterator[Union[bytes, str]]:
        # Pass the rest of the stream to `docker build`
        yield from images.build(request.stream, tag)
        instance_provider.push(tag)
        yield json.dumps({'id': tag})

    return Response(act(), mimetype='text/plain')


@app.route('/data/input/<input_id>', methods=['PUT'])
def put_input_entrypoint(input_id: str):
    return jsonify(
        {'id': input_data_configuration.publish_input_data(
                input_id, get_input_metadata_from_request(), request.stream)})


@app.route('/data/input/<expected_input_id>', methods=['HEAD'])
def check_input_data_entrypoint(expected_input_id: str):
    is_present = input_data_configuration.check_input_data(
        expected_input_id, get_input_metadata_from_request())
    if is_present:
        return jsonify({'id': expected_input_id})
    else:
        abort(requests.codes.not_found)


def get_input_metadata_from_request() -> 'InputMetadata':
    metadata: InputMetadata = InputMetadata()
    metadata.user = request.args.get('user', default=None, type=str)
    metadata.project = request.args.get(
        'project', default=None, type=str)
    metadata.path = request.args.get(
        'path', default=None, type=str)
    metadata.timestamp_millis = request.args.get(
        'timestamp_millis', default=None, type=str)
    if not metadata.has_all_args_or_none():
        abort(request.codes.bad_request)
    return metadata


@app.route('/data/input/id', methods=['GET'])
def get_input_id_entrypoint():
    try:
        metadata = get_input_metadata_from_request()
    except ValueError:
        abort(requests.codes.bad_request)
        return
    id_or_none = input_data_configuration.get_input_id_from_metadata_or_none(
        metadata)
    return jsonify({'id': id_or_none})


@app.route('/data/input/<input_id>', methods=['DELETE'])
def delete_input_data(input_id: str):
    try:
        os.remove(input_data_configuration.input_file(input_id))
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


@app.route(f'/instances/kill', methods=['POST'])
def kill_instances_entrypoint():
    all_of_them_plz: bool = request.json['all_of_them_plz']
    if all_of_them_plz:
        instance_ids = None
    else:
        instance_ids: [str] = request.json['instance_ids']
    force_if_not_idle = request.json['force_if_not_idle']

    status_code = requests.codes.ok
    response_dict = {}
    try:
        instance_provider.kill_instances(
            instance_ids=instance_ids, force_if_not_idle=force_if_not_idle)
    except ProviderKillingInstancesException as e:
        response_dict['failed_instance_ids_to_messages'] = \
            e.instance_ids_to_messages
        status_code = requests.codes.conflict
    except NoInstancesFound:
        response_dict['warning_message'] = 'Request to kill all instances, ' \
                                           'yet no instances were found.'
    response = jsonify(response_dict)
    response.status_code = status_code
    return response


@app.route(f'/executions/describe/<execution_id>', methods=['GET'])
def describe_execution_entrypoint(execution_id: str):
    start_metadata = db_storage.retrieve_start_metadata(execution_id)
    if start_metadata is None:
        raise ExecutionNotFoundException(execution_id)
    return jsonify({'start_metadata': start_metadata})


def get_execution_uuid() -> str:
    # Recommended method for the node if you don't want to disclose the
    # physical address (see Python uuid docs)
    random_node = random.getrandbits(48) | 0x010000000000
    return str(uuid.uuid1(node=random_node))


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
