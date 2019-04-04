import io
import os
import subprocess
import sys

from typing import Optional, List, Any, Tuple, ContextManager

PROJECT_NAME = 'plztest'
NETWORK = os.environ.get('NETWORK', f'{PROJECT_NAME}_default')
VOLUME_PREFIX = f'{PROJECT_NAME}_data_'
CLI_BUILDER_IMAGE = f'{PROJECT_NAME}/cli-builder'
CLI_IMAGE = f'{PROJECT_NAME}/cli'
CLI_CONTAINER_PREFIX = f'{PROJECT_NAME}_cli_'
CONTROLLER_IMAGE = f'{PROJECT_NAME}/controller'
CONTROLLER_CONTAINER = f'{PROJECT_NAME}_controller_1'

# Controller hostname as set by docker compose. For each a host, the
# network includes the service name as well as the container name.
# It's useful to remember that we can also use the service name, as
# the container name, by default, includes a random string. The
# controller just uses "redis" (instead of the redis container name)
# when referring to the redis host for the same reason
CONTROLLER_HOSTNAME = 'controller'
CONTROLLER_TESTS_IMAGE = f'{PROJECT_NAME}/controller-tests'
CONTROLLER_TESTS_CONTAINER = f'{PROJECT_NAME}_controller-tests_1'
CONTROLLER_PORT = 80

TEST_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
DATA_DIRECTORY = f'{os.path.abspath(os.getcwd())}/test_cache/'


def print_info(args: List[Any]):
    _print_with_color('green', args)


def print_warning(args: List[Any]):
    _print_with_color('yellow', args)


def print_error(args: List[Any]):
    _print_with_color('red', args)


def _maybe_reopen_stdout(should_reopen_stdout):
    if should_reopen_stdout:
        os.fdopen(sys.stdout.fileno(), 'wb', buffering=0)
    else:
        return ContextManager()


def execute_command(
        args,
        hide_output: Optional[bool] = False,
        fail_on_failure: Optional[bool] = True,
        file_to_dump_stdout: Optional[io.FileIO] = None,
        substitute_stdout_lines: Optional[List[Tuple[bytes, bytes]]] = None,
        stderr_to_stdout: Optional[bool] = False) -> subprocess.Popen:
    if substitute_stdout_lines is not None:
        substitute_stdout_lines = []
    iterate_stdout = False
    kwargs = {}
    if hide_output:
        kwargs['stdout'] = subprocess.DEVNULL
        kwargs['stderr'] = subprocess.DEVNULL
    if file_to_dump_stdout is not None or len(substitute_stdout_lines) > 0:
        iterate_stdout = True
        kwargs['stdout'] = subprocess.PIPE
    if stderr_to_stdout:
        kwargs['stderr'] = subprocess.STDOUT

    subp = subprocess.Popen(args, shell=True, **kwargs)
    # Reopen stdout as to be able to output bytes (to avoid conversion to
    # strings. as we don't know the encoding of whatever we're running)
    should_reopen_stdout = iterate_stdout and not hide_output
    line_so_far = []
    if iterate_stdout:
        with _maybe_reopen_stdout(
                should_reopen_stdout=should_reopen_stdout) as stdo:
            for c in subp.stdout.read(1):
                if len(substitute_stdout_lines) > 0:

                if not hide_output:
                    stdo.write(c)
                if file_to_dump_stdout is not None:
                    file_to_dump_stdout.write(c)
    if fail_on_failure:
        if subp.returncode != 0:
            sys.exit(subp.returncode)
    return subp


def _print_with_color(color: str, args: List[Any]):
    # Print with color if using the terminal
    for a in args:
        print(a, end='')
    print()


def remove_volume(volume_name: str):
    if container_exists(volume_name):
        execute_command(
            ['docker', 'container', 'kill', volume_name],
            hide_output=True,
            fail_on_failure=False)
        execute_command(
            ['docker', 'container', 'rm', volume_name],
            hide_output=True
        )
    if volume_exists(volume_name):
        execute_command(['docker', 'volume', 'rm', volume_name],
                        hide_output=True)


def container_exists(container_name: str) -> bool:
    completed_process = execute_command(
        ['docker', 'container', 'inspect', container_name],
        hide_output=True,
        fail_on_failure=False)
    return completed_process.returncode == 0


def volume_exists(container_name: str) -> bool:
    completed_process = execute_command(
        ['docker', 'volume', 'inspect', container_name],
        hide_output=True,
        fail_on_failure=False
    )
    return completed_process.returncode == 0
