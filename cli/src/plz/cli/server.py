import functools
from typing import Optional

import requests
import urllib3
from requests import Response

from plz.cli import ssh_session
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException
from plz.cli.ssh_session import add_ssh_channel_adapter


class Server:
    @staticmethod
    def from_configuration(configuration: Configuration):
        connection_info = configuration.connection_info
        return Server(configuration.host, configuration.port, connection_info)

    def __init__(self, host: str, port: int,
                 connection_info: Optional[dict] = None):
        connection_info = connection_info or {}
        self.schema = connection_info.get('schema', 'http')
        self.connection_info = connection_info
        self.prefix = f'{self.schema}://{host}:{port}'

    def request(self, method: str, *path_segments: str, **kwargs) -> Response:
        try:
            url = self.prefix + '/' + '/'.join(path_segments)
            session = requests.session()
            if self.schema == ssh_session.PLZ_SSH_SCHEMA:
                add_ssh_channel_adapter(session, self.connection_info)
            return session.request(method, url, **kwargs)
        except (ConnectionError,
                requests.ConnectionError,
                urllib3.exceptions.NewConnectionError) as e:
            raise CLIException(
                f'We couldn\'t establish a connection to the server.') from e
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
