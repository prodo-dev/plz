import functools
from typing import Optional, Set

import requests
import urllib3
from requests import Response

from plz.cli import ssh_session
from plz.cli.configuration import Configuration
from plz.cli.exceptions import CLIException, RequestException
from plz.cli.ssh_session import add_ssh_channel_adapter
from plz.controller.exceptions import AbortedExecutionException, \
    BadInputMetadataException, ExecutionAlreadyHarvestedException, \
    ExecutionNotFoundException, IncorrectInputIDException, \
    InstanceNotRunningException, InstanceStillRunningException, \
    WorkerUnreachableException, ProviderKillingInstancesException

_EXCEPTION_NAMES_TO_CLASSES = {
    type(e).__name__: e
    for e in (
        AbortedExecutionException,
        BadInputMetadataException,
        ExecutionAlreadyHarvestedException,
        ExecutionNotFoundException,
        IncorrectInputIDException,
        InstanceNotRunningException,
        InstanceStillRunningException,
        ProviderKillingInstancesException,
        WorkerUnreachableException,
    )
}


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

    @staticmethod
    def _maybe_raise_exception(response, codes_with_exceptions):
        response_code = response.status_code
        if response_code in codes_with_exceptions:
            try:
                response_json = response.json()
                assert(isinstance(response_json, dict))
                exception_class = _EXCEPTION_NAMES_TO_CLASSES[
                    response_json['exception_type']]
                del response_json['exception_type']
            except Exception as e:
                raise RequestException(response) from e
            raise exception_class(
                response_code=response_code, **response_json)

    delete = functools.partialmethod(request, 'DELETE')
    get = functools.partialmethod(request, 'GET')
    head = functools.partialmethod(request, 'HEAD')
    options = functools.partialmethod(request, 'OPTIONS')
    patch = functools.partialmethod(request, 'PATCH')
    post = functools.partialmethod(request, 'POST')
    put = functools.partialmethod(request, 'PUT')
