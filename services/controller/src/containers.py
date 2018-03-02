import logging
import subprocess
from typing import Iterator, List, Optional

from images import Images


class Containers:
    log = logging.getLogger('containers')

    def __init__(self, prefix: Optional[List[str]] = None):
        self.prefix = prefix if prefix else []

    def run(self, name: str, tag: str, command: str):
        """
        Runs a command on the instance.
        """

        # IntelliJ doesn't know about the encoding argument, and so thinks that
        # both `stdout` and `stderr` are `bytes`, not `str` objects.
        # All inspection suppressions in this function are related to this.

        image = f'{Images.DOCKER_REPOSITORY}:{tag}'
        invocation = self.prefix + [
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
                not self._is_container_id(container_id):
            raise InvocationException(process, stdout, stderr)
        self.log.info(f'Started container: {container_id}')

    def rm(self, name: str):
        subprocess.run(
            self.prefix + ['docker', 'stop', name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        subprocess.run(
            self.prefix + ['docker', 'rm', name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    def logs(self, name: str) -> Iterator[bytes]:
        process = None
        try:
            invocation = self.prefix + ['docker', 'logs', '--follow', name]
            process = subprocess.Popen(
                invocation,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
            yield from process.stdout
        finally:
            if process is not None and process.returncode is None:
                process.kill()

    @staticmethod
    def _is_container_id(container_id: str):
        if len(container_id) != 64:
            return False
        try:
            int(container_id, 16)
        except ValueError:
            return False
        return True


class InvocationException(Exception):
    def __init__(self, process, stdout, stderr):
        super().__init__(
            f'Error running command.\n'
            f'Exit Status: {process.returncode}\n'
            f'STDOUT: {stdout}\n'
            f'STDERR: {stderr}\n')
