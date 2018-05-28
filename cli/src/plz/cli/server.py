from typing import Sequence

import requests
import urllib3
from requests import Response

from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException


def _method(name: str):
    def impl(self: 'Server', *path_segments: str, **kwargs) -> Response:
        try:
            return requests.request(name, self._url(path_segments), **kwargs)
        except (ConnectionError,
                requests.ConnectionError,
                urllib3.exceptions.NewConnectionError) as e:
            raise CLIException(
                "We couldn't establish a connection to the server.") from e
        except (TimeoutError, requests.Timeout) as e:
            raise CLIException(
                'Our connection to the server timed out.') from e

    return impl


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        return Server(configuration.host, configuration.port)

    def __init__(self, host: str, port: int):
        self.prefix = f'http://{host}:{port}'

    delete = _method('DELETE')
    get = _method('GET')
    head = _method('HEAD')
    options = _method('OPTIONS')
    patch = _method('PATCH')
    post = _method('POST')
    put = _method('PUT')

    def _url(self, path_segments: Sequence[str]) -> str:
        return self.prefix + '/' + '/'.join(path_segments)


http_codes = requests.codes
