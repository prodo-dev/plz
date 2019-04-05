import io
import os
import re
import subprocess
import sys
import traceback

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
PLZ_ROOT_DIRECTORY = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..'))

DATA_DIRECTORY = f'{PLZ_ROOT_DIRECTORY}/test_cache/'


def print_info(*args: Any):
    _print_with_color('green', *args)


def print_warning(*args: Any):
    _print_with_color('yellow', *args)


def print_error(*args: Any):
    _print_with_color('red', *args)


def _maybe_reopen_stdout(should_reopen_stdout):
    if should_reopen_stdout:
        # Pycharm doesn't really know the arguments of fdopen or return value
        # noinspection PyArgumentList
        return os.fdopen(sys.stdout.fileno(), 'wb', buffering=0, closefd=False)
    else:
        return ContextManager()


def execute_command(
        args,
        hide_output: Optional[bool] = False,
        fail_on_failure: Optional[bool] = True,
        file_to_dump_stdout: Optional[io.FileIO] = None,
        substitute_stdout_lines: Optional[List[Tuple[bytes, bytes]]] = None,
        stderr_to_stdout: Optional[bool] = False) -> subprocess.Popen:
    print_info('Running:', ' '.join(args))
    if substitute_stdout_lines is None:
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

    subp = subprocess.Popen(args, bufsize=1, **kwargs)
    # Reopen stdout as to be able to output bytes (to avoid conversion to
    # strings. as we don't know the encoding of whatever we're running)
    should_reopen_stdout = iterate_stdout and not hide_output
    line_so_far = []
    if iterate_stdout:
        with _maybe_reopen_stdout(
               should_reopen_stdout=should_reopen_stdout) as stdo:
            c = subp.stdout.read(1)
            while len(c) > 0:
                if not substitute_stdout_lines:
                    if not hide_output:
                        stdo.write(c)
                    if file_to_dump_stdout is not None:
                        file_to_dump_stdout.write(c)
                if len(substitute_stdout_lines) > 0:
                    line_so_far.append(c)
                    if c[0] == bytes(os.linesep, 'utf-8')[0]:
                        # Pycharm has the wrong return types for Popen
                        # noinspection PyTypeChecker
                        line = b''.join(line_so_far)
                        line_so_far = []
                        for m, r in substitute_stdout_lines:
                            line = re.sub(m, r, line)
                        if not hide_output:
                            stdo.write(line)
                        if file_to_dump_stdout is not None:
                            print('Writing to file!')
                            file_to_dump_stdout.write(line)
                c = subp.stdout.read(1)

            if len(substitute_stdout_lines) > 0 and len(line_so_far) > 0:
                line = b''.join(line_so_far)
                for m, r in substitute_stdout_lines:
                    line = re.sub(m, r, line)
                if not hide_output:
                    stdo.write(line)
                if file_to_dump_stdout is not None:
                    print('Writing to file at end!')
                    file_to_dump_stdout.write(line)
    subp.wait()
    print('Return code is:', subp.returncode)
    if file_to_dump_stdout is not None:
        file_to_dump_stdout.flush()
    if fail_on_failure:
        print('Checking')
        if subp.returncode != 0:
            traceback.print_stack()
            print_error('Error executing:', ' '.join(args))
            sys.exit(subp.returncode)
    return subp


def _print_with_color(color: str, *args: Any):
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
