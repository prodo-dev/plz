from types import GeneratorType

from flask import Flask, jsonify, request, Response
import requests

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
    # TODO(sergio): do the actual thing
    return 'The-id-is-' + command


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


def _stream_binary_generator(generator: GeneratorType) -> Response:
    return Response(generator, mimetype='application/octet-stream')


app.run()
