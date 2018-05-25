from typing import Sequence

import requests
from requests import Response

from plz.cli.configuration import Configuration


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        return Server(configuration.host, configuration.port)

    def __init__(self, host: str, port: int):
        self.prefix = f'http://{host}:{port}'

    def get(self, *path_segments: str) -> Response:
        return requests.get(self._url(path_segments))

    def post(self, *path_segments: str, **kwargs) -> Response:
        return requests.post(self._url(path_segments), **kwargs)

    def _url(self, path_segments: Sequence[str]) -> str:
        return self.prefix + '/' + '/'.join(path_segments)
