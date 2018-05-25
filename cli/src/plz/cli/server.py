import requests

from plz.cli.configuration import Configuration


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        return Server(configuration.host, configuration.port)

    def __init__(self, host: str, port: int):
        self.prefix = f'http://{host}:{port}'

    def get(self, path: str):
        return requests.get(self._url(path))

    def post(self, path: str, **kwargs):
        return requests.post(self._url(path), **kwargs)

    def _url(self, path: str):
        return self.prefix + '/' + path
