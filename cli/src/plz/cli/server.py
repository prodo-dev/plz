import requests

from plz.cli.configuration import Configuration


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        return Server(configuration.host, configuration.port)

    def __init__(self, host: str, port: int):
        self.prefix = f'http://{host}:{port}'

    def get(self, path: str):
        return requests.get(self.prefix + '/' + path)
