import os
import socket
import threading

from paramiko import Channel, ChannelFile, HostKeys, PKey, RSAKey, Transport
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3 import HTTPConnectionPool
from urllib3.connection import HTTPConnection

from plz.cli.exceptions import CLIException

PLZ_SSH_SCHEMA = 'plz-ssh'


def add_ssh_channel_adapter(session: Session, connection_info: dict):
    """For sessions in ssh channels, use the same adapter as for http. We
       instruct the adapter that, for our schema, the pool connection
       manager creates SSH channels, instead of sockets."""

    #
    # Modify the http adapter to create ssh channels
    #
    http_adapter = HTTPAdapter()
    poolmanager = http_adapter.poolmanager
    # Obtain keys for connections same as for http
    poolmanager.key_fn_by_scheme[PLZ_SSH_SCHEMA] = \
        poolmanager.key_fn_by_scheme['http']
    # Use a pool that creates SSH channels
    poolmanager.pool_classes_by_scheme[PLZ_SSH_SCHEMA] = \
        type(
            'SSHChannelHTTPConnectionPoolWithInfo',
            (SSHChannelHTTPConnectionPool,),
            {'connection_info': connection_info})

    #
    # Map the schema to the adapter
    #
    session.mount(f'{PLZ_SSH_SCHEMA}', http_adapter)


class SSHChannelHTTPConnection(HTTPConnection):
    connection_info = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def connect(self):
        username = self.connection_info.get('username', 'plz-user')
        path_to_private_key = self.connection_info['path_to_private_key']
        try:
            transport = _get_transport(
                hostname=self.host, username=username,
                path_to_private_key=path_to_private_key)
            ch = transport.open_channel(
                'direct-tcpip', ('0.0.0.0', self.port), ('0.0.0.0', 0))
            _override_makefile(ch)
            _override_channel_close(ch)
            self._prepare_conn(ch)
        except Exception as e:
            raise SSHAuthenticationError('Creating channel: ') from e


class SSHChannelHTTPConnectionPool(HTTPConnectionPool):
    connection_info = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        connection_info = self.connection_info
        self.ConnectionCls = type(
            'SSHChannelHTTPConnectionWithInfo',
            (SSHChannelHTTPConnection,),
            {'connection_info': connection_info})


def _override_makefile(ch: Channel):
    # When doing makefile on a channel, store a pointer to the file, so that
    # when trying to close the channel we can check if the file is still open
    # and leave the closure pending. Override the close method in the file as
    # to execute the pending closure if needed.
    ch.channel_file = None

    def do_makefile(*args):
        if ch.channel_file is None:
            ch.channel_file = Channel.makefile(ch, *args)
            _override_file_close(ch.channel_file)
            return ch.channel_file
        else:
            raise FileExistsError('We allow only one file per channel')
    ch.makefile = do_makefile


def _override_file_close(channel_file: ChannelFile):
    channel_file.channel.close_pending = False

    def do_close():
        ChannelFile.close(channel_file)
        if channel_file.channel.close_pending:
            channel_file.channel.close()
    return do_close


def _override_channel_close(ch: Channel):
    ch.channel_file = None
    ch.close_pending = False

    def do_close():
        if ch.channel_file is not None and not ch.channel_file.closed:
            ch.close_pending = True
            return
        else:
            return Channel.close(ch)
    ch.close = do_close


_transport = None
_transport_lock = threading.RLock()


def _get_transport(hostname: str, username: str, path_to_private_key: str):
    global _transport, _transport_lock
    with _transport_lock:
        if _transport is None:
            key = RSAKey.from_private_key_file(path_to_private_key)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((hostname, 22))

            # noinspection PyTypeChecker
            _transport = Transport(sock)
            _transport.connect(
                None, username=username, password='', pkey=key)
            _validate_key(hostname, _transport.get_remote_server_key())
            if not _transport.is_authenticated():
                raise SSHAuthenticationError(
                    'Couldn\'t authenticate the ssh transport')
        return _transport


def _validate_key(host: str, server_key: PKey):
    known_hosts_file = '~/.ssh/known_hosts'
    host_keys = HostKeys()
    host_keys.load(os.path.expanduser(known_hosts_file))
    known_server_keys = host_keys.get(host)
    if known_server_keys is None:
        raise SSHAuthenticationError(
            'plz host is not known. You can add the host key with `\n'
            f'ssh-keyscan -H {host} >> {known_hosts_file}\n`')
    known_server_keys = host_keys.get(host)
    if known_server_keys.get(server_key.get_name()) is None:
        raise SSHAuthenticationError(
            f'No key found for host {host} with name {server_key.get_name()}')
    if server_key != known_server_keys.get(server_key.get_name()):
        raise SSHAuthenticationError(
            f'Bad host key for `{host}`. Fix your `{known_hosts_file}` file')


class SSHAuthenticationError(CLIException):
    def __init__(self, message):
        super().__init__(message)
