import multiprocessing
import os
import socket
import unittest
from contextlib import closing

import flask
import requests

from plz.cli.server import Server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.host = 'localhost'
        self.port = find_free_port()
        self.app = create_app()
        latch = multiprocessing.Condition()

        def start_app():
            self.app.run(host='localhost', port=self.port)
            with latch:
                latch.notify()

        app_thread = multiprocessing.Process(target=start_app)
        with latch:
            app_thread.start()
            latch.wait(timeout=1)

    def tearDown(self):
        requests.post(f'http://{self.host}:{self.port}/shutdown')

    def test_makes_a_GET_request(self):
        server = Server(host=self.host, port=self.port)
        response = server.get('get')
        self.assertEqual(response.status_code, requests.codes.ok)
        self.assertEqual(response.text, 'Hello, World!')


def create_app():
    app = flask.Flask(__name__)
    app.debug = False

    # Disable the Flask startup message
    os.environ['WERKZEUG_RUN_MAIN'] = 'true'

    @app.route('/get', methods=['GET'])
    def get_endpoint():
        return 'Hello, World!'

    @app.route('/shutdown', methods=['POST'])
    def shutdown():
        flask.request.environ.get('werkzeug.server.shutdown')()
        return flask.Response()

    return app


def find_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        return s.getsockname()[1]
