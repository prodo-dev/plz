import multiprocessing
import os
import socket
import unittest
from contextlib import closing

# noinspection PyPackageRequirements
import flask
import requests

from plz.cli.exceptions import CLIException
from plz.cli.server import Server


class ServerTest(unittest.TestCase):
    host = None
    port = None
    app = None

    @classmethod
    def setUpClass(cls):
        cls.host = 'localhost'
        cls.port = find_free_port()
        cls.app = create_app()
        latch = multiprocessing.Condition()

        def start_app():
            cls.app.run(host='localhost', port=cls.port)
            with latch:
                latch.notify()

        app_thread = multiprocessing.Process(target=start_app)
        with latch:
            app_thread.start()
            latch.wait(timeout=1)

    @classmethod
    def tearDownClass(cls):
        requests.post(f'http://{cls.host}:{cls.port}/shutdown')

    def test_makes_a_GET_request(self):
        server = Server(host=self.host, port=self.port)
        response = server.get('get')
        self.assertEqual(response.status_code, requests.codes.ok)
        self.assertEqual(response.text, 'Hello, World!')

    def test_makes_a_POST_request(self):
        server = Server(host=self.host, port=self.port)
        response = server.post('uppercase', data='this is lowercase')
        self.assertEqual(response.status_code, requests.codes.ok)
        self.assertEqual(response.text, 'THIS IS LOWERCASE')

    def test_makes_a_DELETE_request(self):
        server = Server(host=self.host, port=self.port)
        response = server.delete('delete')
        self.assertEqual(response.status_code, requests.codes.not_found)

    def test_compose_paths_from_segments(self):
        server = Server(host=self.host, port=self.port)
        response = server.get('one', 'two', 'three')
        self.assertEqual(response.status_code, requests.codes.ok)
        self.assertEqual(response.text, '123')

    def test_handles_connection_errors(self):
        server = Server(host=self.host, port=self.port + 1)
        with self.assertRaises(CLIException) as cm:
            server.get()
        self.assertEqual(
            cm.exception.args[0],
            "We couldn't establish a connection to the server.")

    def test_handles_timeouts(self):
        server = Server(host=self.host, port=self.port)
        with self.assertRaises(CLIException) as cm:
            server.get(timeout=0.00001)
        self.assertEqual(
            cm.exception.args[0], 'Our connection to the server timed out.')


def create_app():
    app = flask.Flask(__name__)
    app.debug = False

    # Disable the Flask startup message
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'

    @app.route('/get', methods=['GET'])
    def get_endpoint():
        return 'Hello, World!'

    @app.route('/one/two/three', methods=['GET'])
    def deep_endpoint():
        return '123'

    @app.route('/uppercase', methods=['POST'])
    def post_endpoint():
        body: str = flask.request.data
        return body.upper()

    @app.route('/delete', methods=['DELETE'])
    def delete_endpoint():
        return flask.Response(status=requests.codes.not_found)

    @app.route('/shutdown', methods=['POST'])
    def shutdown():
        flask.request.environ.get('werkzeug.server.shutdown')()
        return flask.Response()

    return app


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
