
import os
import socket

import paramiko
from paramiko import Channel

default_path = os.path.join(os.environ['HOME'], 'plz', 'secrets', 'keys',
                            'id_rsa')
key = paramiko.RSAKey.from_private_key_file(default_path)

hostname = 'plz.sergio.test.inside.prodo.ai'
port = 22

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((hostname, port))


t = paramiko.Transport(sock)
t.connect(None, 'ubuntu', password=None, pkey=key)
if t.is_authenticated():
    print('Yes!')
else:
    print('Fuck...')
ch: Channel = t.open_channel('direct-tcpip', ('0.0.0.0', 80), ('', 0))
print(ch.send('GET /executions/list HTTP/1.0\r\n\r\n'))
print(ch.recv(1000))
