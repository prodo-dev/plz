import logging
import select
import subprocess
from typing import Iterator, List, Optional

DOCKER_REPOSITORY = \
    '024444204267.dkr.ecr.eu-west-1.amazonaws.com/batman/builds'

log = logging.getLogger('invocations')


def docker_run(name: str, tag: str, command: str,
               prefix: Optional[List[str]] = None):
    """
    Runs a command on the instance.
    """

    # IntelliJ doesn't know about the encoding argument, and so thinks that
    # both `stdout` and `stderr` are `bytes`, not `str` objects.
    # All suppresions in this function are related to this.

    prefix = prefix if prefix else []
    image = f'{DOCKER_REPOSITORY}:{tag}'
    invocation = prefix + [
        'docker', 'run',
        '--detach',
        '--name', name,
        image,
        'sh', '-c', command,
    ]

    # noinspection PyArgumentList
    process = subprocess.Popen(
        invocation,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf-8')
    stdout, stderr = process.communicate()

    # noinspection PyTypeChecker
    container_id = stdout.rstrip('\n')
    # noinspection PyTypeChecker
    if stderr != '' or process.returncode != 0 or \
            not is_container_id(container_id):
        raise InvocationException(process, stdout, stderr)
    log.info(f'Started container: {container_id}')


def docker_rm(name: str,
              prefix: Optional[List[str]] = None):
    prefix = prefix if prefix else []
    subprocess.run(
        prefix + ['docker', 'stop', name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    subprocess.run(
        prefix + ['docker', 'rm', name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)


def docker_logs(name: str, prefix: Optional[List[str]] = None)\
        -> Iterator[bytes]:
    prefix = prefix if prefix else []
    process = None
    try:
        command = f'docker logs {name} -f 2>&1'
        invocation = prefix + [command]
        process = subprocess.Popen(
            invocation,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        # Note: the docs indicate to use process.communicate() instead of
        # process.stdout and process.stderr due to the possibility of
        # deadlocks. As far I understand, the problem occurs when the internal
        # buffers are full, causing the child process to block (which in our
        # case is not a problem). See here:
        # https://thraxil.org/users/anders/posts/2008/03/13/Subprocess-Hanging-PIPE-is-your-enemy/
        # We cannot it use communicate as it waits for the process to finish.
        # An alternative would be to use a `tempfile.TemporaryFile`.
        # Do not use this code in other parts if you don't want to deadlock.
        out = None
        stderr = None
        while out is None or len(out):
            out = process.stdout.read1(1024)
            # Poll stderr to see if there's something
            # (using peek might block if there's nothing)
            stderr_to_read, _, _ = select.select(
                [process.stderr.fileno()], [], [], 0.1)
            if stderr_to_read:
                # Using peek: read might block if the process hasn't finished,
                # read1 requires an argument for the maximum size. If there's
                # actually something we won't keep reading, so using peek is
                # OK
                stderr = process.stderr.peek()
                # Check the length, if the process is already finished we
                # might be reading the empty bytes, and there was no error
                if len(stderr):
                    raise InvocationException(process, out, stderr)
            yield out
        # Get the return code
        try:
            process.communicate(timeout=0.01)
        except subprocess.TimeoutExpired:
            pass
        if process.returncode is None or process.returncode != 0:
            raise InvocationException(process, out, stderr)
    finally:
        if process is not None and process.returncode is None:
            process.kill()


class InvocationException(Exception):
    def __init__(self, process, stdout, stderr):
        super().__init__(
            f'Error running command.\n'
            f'Exit Status: {process.returncode}\n'
            f'STDOUT: {stdout}\n'
            f'STDERR: {stderr}\n')


def is_container_id(container_id: str):
    if len(container_id) != 64:
        return False
    try:
        int(container_id, 16)
    except ValueError:
        return False
    return True
