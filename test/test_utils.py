import io
import os
import re
import shutil
import subprocess
import sys
import traceback
from typing import Any, ContextManager, List, Optional, Tuple

PROJECT_NAME = 'plztest'
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
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
COVERAGE_RESULTS_DIRECTORY = os.path.join(TEST_DIRECTORY, 'coverage',
                                          'results')

DATA_DIRECTORY = f'{PLZ_ROOT_DIRECTORY}/test_cache/'
REDIS_DATA_DIRECTORY = f'{DATA_DIRECTORY}/redis_data/'
PLZ_USER = 'plztest'


def get_network():
    return os.environ.get('NETWORK', f'{PROJECT_NAME}_default')


def print_info(*args: Any):
    _print_with_color('green', *args)


def print_warning(*args: Any):
    _print_with_color('yellow', *args)


def print_error(*args: Any):
    _print_with_color('red', *args)


def print_debug(*args: Any):
    if 'PLZ_TEST_DEBUG' in os.environ:
        _print_with_color('blue', *args)


class EmptyContextManager(ContextManager):
    def __exit__(self, *args):
        pass


def _maybe_reopen_stdout(should_reopen_stdout):
    if should_reopen_stdout:
        # Pycharm doesn't really know the arguments of fdopen or return value
        # noinspection PyArgumentList
        return os.fdopen(sys.stdout.fileno(), 'wb', buffering=0, closefd=False)
    else:
        return EmptyContextManager()


def execute_command(
        args: [str],
        hide_output: bool = False,
        hide_stderr: bool = False,
        fail_on_failure: bool = True,
        file_to_dump_stdout: Optional[io.FileIO] = None,
        substitute_stdout_lines: Optional[List[Tuple[bytes, bytes]]] = None,
        stderr_to_stdout: bool = False,
        env: Optional[dict] = None,
        stdout_holder: Optional[List[bytes]] = None) -> subprocess.Popen:
    if substitute_stdout_lines is None:
        substitute_stdout_lines = []
    if env is None:
        env = os.environ
    print_debug('Running:', ' '.join(args))
    iterate_stdout = False
    kwargs = {}
    if hide_output:
        kwargs['stdout'] = subprocess.DEVNULL
    if hide_stderr:
        kwargs['stderr'] = subprocess.DEVNULL
    if file_to_dump_stdout is not None or len(substitute_stdout_lines) > 0 \
            or stdout_holder is not None:
        iterate_stdout = True
        kwargs['stdout'] = subprocess.PIPE
    if stderr_to_stdout:
        kwargs['stderr'] = subprocess.STDOUT

    subp = subprocess.Popen(args, bufsize=1, env=env, **kwargs)
    # Reopen stdout as to be able to output bytes (to avoid conversion to
    # strings. as we don't know the encoding of whatever we're running)
    should_reopen_stdout = iterate_stdout and not hide_output
    line_so_far = []
    if iterate_stdout:
        with _maybe_reopen_stdout(
                should_reopen_stdout=should_reopen_stdout) as stdo:

            def write_to_stdo(bs: bytes):
                if not hide_output:
                    stdo.write(bs)
                if file_to_dump_stdout is not None:
                    file_to_dump_stdout.write(bs)
                if stdout_holder is not None:
                    stdout_holder.append(bs)

            c: bytes = subp.stdout.read(1)
            while len(c) > 0:
                if len(substitute_stdout_lines) == 0:
                    write_to_stdo(c)
                else:
                    line_so_far.append(c)
                    if c[0] == bytes(os.linesep, 'utf-8')[0]:
                        # Pycharm has the wrong return types for Popen
                        # noinspection PyTypeChecker
                        line = b''.join(line_so_far)
                        line_so_far = []
                        for m, r in substitute_stdout_lines:
                            line = re.sub(m, r, line)
                        write_to_stdo(line)
                c = subp.stdout.read(1)

            if len(substitute_stdout_lines) > 0 and len(line_so_far) > 0:
                line = b''.join(line_so_far)
                for m, r in substitute_stdout_lines:
                    line = re.sub(m, r, line)
                write_to_stdo(line)
    subp.wait()
    print_debug('Return code is:', subp.returncode)
    if file_to_dump_stdout is not None:
        file_to_dump_stdout.flush()
    if fail_on_failure:
        if subp.returncode != 0:
            traceback.print_stack()
            print_error('Error executing:', ' '.join(args))
            sys.exit(subp.returncode)
    return subp


def _print_with_color(color: str, *args: Any):
    is_a_tty = sys.stdout.isatty()
    color_to_int = {'red': 31, 'yellow': 33, 'green': 32, 'blue': 34}
    if is_a_tty:
        print(f'\x1b[{color_to_int[color]}m', end='')
    print('> ', end='')
    if is_a_tty:
        print('\x1b[0m', end='')
    for a in args:
        print(a, end='')
    print()


def remove_volume(volume_name: str):
    if container_exists(volume_name):
        execute_command(['docker', 'container', 'kill', volume_name],
                        hide_output=True,
                        hide_stderr=True,
                        fail_on_failure=False)
        execute_command(['docker', 'container', 'rm', volume_name],
                        hide_output=True)
    if volume_exists(volume_name):
        execute_command(['docker', 'volume', 'rm', volume_name],
                        hide_output=True)


def container_exists(container_name: str) -> bool:
    completed_process = execute_command(
        ['docker', 'container', 'inspect', container_name],
        hide_output=True,
        hide_stderr=True,
        fail_on_failure=False)
    return completed_process.returncode == 0


def volume_exists(container_name: str) -> bool:
    completed_process = execute_command(
        ['docker', 'volume', 'inspect', container_name],
        hide_output=True,
        hide_stderr=True,
        fail_on_failure=False)
    return completed_process.returncode == 0


def cleanup(interrupted: bool):
    def rm_on_error_handler(func, path, exc_info):
        print_error(f'Error deleting [{path}]:', func, exc_info)

    if os.path.isdir(DATA_DIRECTORY):
        shutil.rmtree(DATA_DIRECTORY, onerror=rm_on_error_handler)
    stop_all_clis()
    stop_controller()
    stop_all_test_containers()
    stop_container(CONTROLLER_TESTS_CONTAINER)
    remove_all_volumes()
    if interrupted:
        sys.exit(1)


# Signal handler
def sig_cleanup(_, __):
    cleanup(interrupted=True)


class DoCleanupContextManager(ContextManager):
    def __init__(self):
        self.interrupted = False

    def __exit__(self, *args):
        cleanup(self.interrupted)


def stop_container(container_name: str):
    if not container_exists(container_name):
        return
    execute_command(['docker', 'container', 'stop', container_name],
                    hide_output=True,
                    fail_on_failure=False)
    execute_command(['docker', 'container', 'rm', container_name],
                    hide_output=True,
                    fail_on_failure=False)


def remove_all_volumes():
    stdout_holder: List[bytes] = []
    execute_command([
        'docker', 'volume', 'ls', '--quiet', f'--filter=name={VOLUME_PREFIX}'
    ],
                    stdout_holder=stdout_holder)
    volumes = str(b''.join(stdout_holder), 'utf-8').splitlines()
    for volume in volumes:
        remove_volume(volume)


def stop_all_clis():
    stdout_holder: List[bytes] = []
    execute_command([
        'docker', 'container', 'ls', '--quiet', '--all',
        f'--filter=name={CLI_CONTAINER_PREFIX}'
    ],
                    stdout_holder=stdout_holder)
    containers = b''.join(stdout_holder)
    for container in str(containers, 'utf-8').splitlines():
        stop_container(container)


def stop_controller():
    if running_with_coverage():
        # Unless we interrupt the server before stopping, coverage won't write
        # the report
        execute_command(
            ['docker', 'kill', '--signal=INT', CONTROLLER_CONTAINER])
        execute_command([
            'docker', 'container', 'cp',
            f'{CONTROLLER_CONTAINER}:/src/controller.coverage',
            os.path.join(COVERAGE_RESULTS_DIRECTORY, 'controller.coverage')
        ])
    docker_compose('stop')
    docker_compose('logs')
    docker_compose('down', '--volumes')


def stop_all_test_containers():
    stdout_holder = []
    execute_command([
        'docker', 'container', 'ls', '-a', '--filter=name=plz.execution.id.',
        '--format={{.ID}}#{{.Image}}'
    ],
                    stdout_holder=stdout_holder,
                    hide_output=True)
    for l in str(b''.join(stdout_holder), 'utf-8').splitlines():
        container_id, image = l.split('#', 1)
        if image.startswith(f'plz/builds:{PLZ_USER}-'):
            stop_container(container_id)


def docker_compose(*args):
    # Specify the container name, as to avoid the random suffix added by docker
    # compose
    env = os.environ.copy()
    env['PROJECT_NAME'] = PROJECT_NAME
    env['CONTROLLER_CONTAINER'] = CONTROLLER_CONTAINER
    env['DATA_DIRECTORY'] = DATA_DIRECTORY
    env['REDIS_DATA_DIRECTORY'] = REDIS_DATA_DIRECTORY
    execute_command([
        'docker-compose', f'--project-name={PROJECT_NAME}',
        f'--file={os.path.join(TEST_DIRECTORY, "docker-compose.yml")}', *args
    ],
                    env=env)


def running_with_coverage():
    return os.environ.get('RUN_WITH_COVERAGE', '') != ''
