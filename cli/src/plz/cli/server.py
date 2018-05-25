from typing import Sequence

import requests
from requests import Response

from plz.cli.configuration import Configuration


def _method(name: str):
    def impl(self, *path_segments: str, **kwargs) -> Response:
        return requests.request(name, self._url(path_segments), **kwargs)

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
