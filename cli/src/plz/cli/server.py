import functools

import requests
import urllib3
from requests import Response

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        return Server(configuration.host, configuration.port)

    def __init__(self, host: str, port: int):
        self.prefix = f'http://{host}:{port}'

    def request(self, method: str, *path_segments: str, **kwargs) -> Response:
        try:
            url = self.prefix + '/' + '/'.join(path_segments)
            return requests.request(method, url, **kwargs)
        except (ConnectionError,
                requests.ConnectionError,
                urllib3.exceptions.NewConnectionError) as e:
            raise CLIException(
                "We couldn't establish a connection to the server.") from e
        except (TimeoutError, requests.Timeout) as e:
            raise CLIException(
                'Our connection to the server timed out.') from e

    delete = functools.partialmethod(request, 'DELETE')
    get = functools.partialmethod(request, 'GET')
    head = functools.partialmethod(request, 'HEAD')
    options = functools.partialmethod(request, 'OPTIONS')
    patch = functools.partialmethod(request, 'PATCH')
    post = functools.partialmethod(request, 'POST')
    put = functools.partialmethod(request, 'PUT')


http_codes = requests.codes
