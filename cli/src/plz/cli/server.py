import functools
from typing import Optional, Set

import requests
import urllib3
from requests import Response

from plz.cli import ssh_session
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException, RequestException
from plz.cli.ssh_session import add_ssh_channel_adapter
from plz.controller.api.exceptions import EXCEPTION_NAMES_TO_CLASSES


class Server:
    @staticmethod
    def from_configuration(
            configuration: Configuration):
        connection_info = configuration.connection_info
        return Server(
            host=configuration.host,
            port=configuration.port,
            connection_info=connection_info)

    def __init__(self, host: str, port: int,
                 exception_names_to_classes: Optional[dict] = None,
                 connection_info: Optional[dict] = None):
        self.exceptions_names_to_classes = exception_names_to_classes or \
            EXCEPTION_NAMES_TO_CLASSES
        connection_info = connection_info or {}
        self.schema = connection_info.get('schema', 'http')
        self.connection_info = connection_info
        self.prefix = f'{self.schema}://{host}:{port}'

    def request(self, method: str, *path_segments: str,
                codes_with_exceptions: Optional[Set[int]] = None, **kwargs) \
            -> Response:
        codes_with_exceptions = codes_with_exceptions or set()
        try:
            url = self.prefix + '/' + '/'.join(path_segments)
            session = requests.session()
            if self.schema == ssh_session.PLZ_SSH_SCHEMA:
                add_ssh_channel_adapter(session, self.connection_info)
            response = session.request(method, url, **kwargs)
            self._maybe_raise_exception(response, codes_with_exceptions)
            return response
        except (ConnectionError,
                requests.ConnectionError,
                urllib3.exceptions.NewConnectionError) as e:
            raise CLIException(
                f'We couldn\'t establish a connection to the server.') from e
        except (TimeoutError, requests.Timeout) as e:
            raise CLIException(
                'Our connection to the server timed out.') from e

    def _maybe_raise_exception(self, response, codes_with_exceptions):
        response_code = response.status_code
        if response_code in codes_with_exceptions:
            try:
                response_json = response.json()
                assert(isinstance(response_json, dict))
                exception_class = self.exceptions_names_to_classes[
                    response_json['exception_type']]
                del response_json['exception_type']
            except Exception as e:
                raise RequestException(response) from e
            raise exception_class(**response_json)

    delete = functools.partialmethod(request, 'DELETE')
    get = functools.partialmethod(request, 'GET')
    head = functools.partialmethod(request, 'HEAD')
    options = functools.partialmethod(request, 'OPTIONS')
    patch = functools.partialmethod(request, 'PATCH')
    post = functools.partialmethod(request, 'POST')
    put = functools.partialmethod(request, 'PUT')
