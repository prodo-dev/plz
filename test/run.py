import argparse
import multiprocessing
import os
import re
import signal
import sys
from glob import glob
from typing import List, Optional, Set

import test_utils
from run_end_to_end_test import run_end_to_end_test
from test_utils import CLI_BUILDER_IMAGE, CLI_IMAGE, \
    CONTROLLER_CONTAINER, CONTROLLER_HOSTNAME, CONTROLLER_IMAGE, \
    CONTROLLER_PORT, CONTROLLER_TESTS_CONTAINER, CONTROLLER_TESTS_IMAGE, \
    DATA_DIRECTORY, PLZ_ROOT_DIRECTORY, PLZ_USER, TEST_DIRECTORY, \
    docker_compose, get_network


def start_controller():
    test_utils.print_info('Building the controller...')
    test_utils.execute_command([
        'docker',
        'image',
        'build',
        '--quiet',
        f'--tag={CONTROLLER_IMAGE}',
        os.path.join(PLZ_ROOT_DIRECTORY,
                     'services/controller')
    ])

    test_utils.stop_container(CONTROLLER_CONTAINER)

    test_utils.print_info('Starting the controller...')
    docker_compose('up', '--build', '--quiet-pull', '--detach')


def build_cli():
    test_utils.print_info('Building the CLI...')
    test_utils.execute_command([
        'docker',
        'image',
        'build',
        '--quiet',
        '--target=builder',
        f'--tag={CLI_BUILDER_IMAGE}',
        f'--file={os.path.join(PLZ_ROOT_DIRECTORY, "cli", "Dockerfile")}',
        PLZ_ROOT_DIRECTORY
    ])
    test_utils.execute_command([
        'docker',
        'image',
        'build',
        '--quiet',
        f'--tag={CLI_IMAGE}',
        f'--file={os.path.join(PLZ_ROOT_DIRECTORY, "cli", "Dockerfile")}',
        PLZ_ROOT_DIRECTORY
    ])


def run_controller_tests(network: str,
                         plz_host: str,
                         plz_port: int,
                         controller_tests_parameters: List[str]) -> bool:
    test_utils.stop_container(CONTROLLER_TESTS_CONTAINER)
    test_utils.execute_command([
        'docker',
        'image',
        'build',
        '--quiet',
        f'--tag={CONTROLLER_TESTS_IMAGE}',
        f'--file={os.path.join(TEST_DIRECTORY, "controller", "Dockerfile")}',
        PLZ_ROOT_DIRECTORY
    ])

    test_utils.print_info('Running controller tests')

    subp = test_utils.execute_command([
        'docker',
        'run',
        '--name',
        CONTROLLER_TESTS_CONTAINER,
        f'--network={network}',
        f'--env=PLZ_HOST={plz_host}',
        f'--env=PLZ_PORT={plz_port}',
        f'--env=PLZ_USER={PLZ_USER}',
        f'--env=PLZ_PROJECT=controller-tests',
        CONTROLLER_TESTS_IMAGE,
        *controller_tests_parameters
    ],
                                      fail_on_failure=False)
    return subp.returncode == 0


def get_end_to_end_tests(
        command_line_specified_tests: Optional[List[str]] = None) -> [str]:
    if command_line_specified_tests is None \
            or len(command_line_specified_tests) == 0:
        end_to_end_tests = []
        # Run all tests, except in directories named "*.ignored"
        for tdir in glob(os.path.join(TEST_DIRECTORY, 'end-to-end', '*', '*')):
            if os.path.isfile(os.path.join(tdir, 'plz.config.json')) \
                    and '.ignored' not in tdir:
                end_to_end_tests.append(
                    # Remove the dir path until end-to-end
                    tdir[len(os.path.join(TEST_DIRECTORY,
                                          '')):])
        return end_to_end_tests

    # Run selected tests.
    # But first, verify all arguments are actually test directories
    for tdir in command_line_specified_tests:
        # Remove trailing slash if present
        if tdir.endswith(os.sep):
            tdir = tdir[:-len(os.sep)]
        if re.search(r'^end-to-end/[A-Za-z0-9\-]+/[A-Za-z0-9\-]+$',
                     tdir) is None \
                or not os.path.isfile(
                    os.path.join(
                        TEST_DIRECTORY, tdir, 'plz.config.json')):
            raise ValueError(f'{tdir} is not a test directory')
    return command_line_specified_tests


def _run_test_piping_output(run_end_to_end_test_args: dict,
                            output_pipe: multiprocessing.Pipe()):
    os.dup2(output_pipe.fileno(), sys.stdout.fileno())
    run_end_to_end_test(**run_end_to_end_test_args)


def run_end_to_end_tests(
        network: str,
        plz_host: str,
        plz_port: int,
        bless: bool,
        in_parallel: bool,
        command_line_specified_tests: Optional[List[str]] = None) -> Set[str]:
    end_to_end_tests = get_end_to_end_tests(command_line_specified_tests)

    if in_parallel:
        pool = multiprocessing.Pool(processes=len(end_to_end_tests))
        pipe_pairs = [multiprocessing.Pipe() for _ in end_to_end_tests]
        process_args = [({
            'network': network,
            'plz_host': plz_host,
            'plz_port': plz_port,
            'bless': bless,
            'test_name': end_to_end_tests[i]
        },
                         output_pipe) for i,
                        (_,
                         output_pipe) in enumerate(pipe_pairs)]
        readers = [os.fdopen(r.fileno(), 'r') for r, _ in pipe_pairs]
        pool_result = pool.starmap_async(_run_test_piping_output, process_args)

        result_ready = False
        while not result_ready:
            if pool_result.ready():
                result_ready = True
            for reader in readers:
                while True:
                    line = reader.readline()
                    if len(line) == 0:
                        break
                    print(line)
        if not pool_result.successful():
            test_utils.print_error('Some tests failed to run')
            test_utils.print_error('Tests:', end_to_end_tests)
            test_utils.print_error('Result:', pool_result.get())
            return set(end_to_end_tests)

        return set(t for i,
                   t in enumerate(end_to_end_tests)
                   if not pool_result.get()[i])
    else:
        failed_tests = set()
        for test_name in end_to_end_tests:
            success = run_end_to_end_test(network,
                                          plz_host,
                                          plz_port,
                                          test_name,
                                          bless)
            if not success:
                failed_tests.add(test_name)
        return failed_tests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('test_dirs', nargs='*', type=str, default=None)
    parser.add_argument('--controller-tests-parameters',
                        type=str,
                        nargs='+',
                        default=[])
    parser.add_argument('--bless', action='store_true', default=False)
    parser.add_argument('--in-parallel', action='store_true', default=False)
    parser.add_argument('--end-to-end-only',
                        action='store_true',
                        default=False)
    parser.add_argument('--controller-tests-only',
                        action='store_true',
                        default=False)
    parser.add_argument('--clean-up-first', action='store_true', default=False)

    options = parser.parse_args(sys.argv[1:])

    if options.end_to_end_only and options.controller_tests_only:
        raise ValueError('Options end_to_end_only and controller_tests_only '
                         'can\'t be specified simultaneously')
    end_to_end_only = options.end_to_end_only \
        or len(options.test_dirs or []) > 0

    end_to_end_tests = end_to_end_only or not options.controller_tests_only
    controller_tests = options.controller_tests_only or not end_to_end_only

    if options.clean_up_first:
        test_utils.cleanup(interrupted=False)

    signal.signal(signal.SIGTERM, test_utils.sig_cleanup)
    with test_utils.DoCleanupContextManager() as cleanup_manager:
        try:
            passed = True
            os.makedirs(DATA_DIRECTORY, exist_ok=True)
            if end_to_end_tests:
                build_cli()

            if 'PLZ_HOST' in os.environ:
                plz_host = os.environ['PLZ_HOST']
                if 'PLZ_PORT' not in os.environ:
                    raise ValueError(
                        'PLZ_HOST is defined but PLZ_PORT is not!')
                plz_port = int(os.environ['PLZ_PORT'])
                network = 'host'
            else:
                start_controller()
                plz_host = CONTROLLER_HOSTNAME
                plz_port = CONTROLLER_PORT
                network = get_network()

            if controller_tests:
                if not run_controller_tests(
                        network,
                        plz_host,
                        plz_port,
                        options.controller_tests_parameters):
                    test_utils.print_error('Some controller tests failed!')
                    passed = False

            if end_to_end_tests:
                failed_tests = run_end_to_end_tests(network,
                                                    plz_host,
                                                    plz_port,
                                                    options.bless,
                                                    options.in_parallel,
                                                    options.test_dirs)
                if len(failed_tests) != 0:
                    passed = False
                    test_utils.print_error('Some end-to-end tests failed!')
                for t in failed_tests:
                    test_utils.print_error(t)
        except InterruptedError:
            cleanup_manager.interrupted = True
            raise

    return 1 if not passed else 0


if __name__ == '__main__':
    sys.exit(main())
