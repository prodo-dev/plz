import argparse
import datetime
import json
import os
import re
import sys
from tempfile import NamedTemporaryFile, TemporaryDirectory, TemporaryFile

import test_utils
from test_utils import CLI_CONTAINER_PREFIX, DATA_DIRECTORY, NETWORK, \
    PLZ_ROOT_DIRECTORY, VOLUME_PREFIX


def run_test(plz_host: str, plz_port: int, test_name: str, bless: bool) \
        -> bool:
    """
    :param plz_host: host where the controller is running
    :param plz_port: port where controller is listening
    :param test_name: name of the test to run (path from test/)
    :param bless: whether to override the expected output and logs with the
           results of the run
    :return: whether the test passed
    """

    if not os.path.exists(DATA_DIRECTORY):
        os.mkdir(DATA_DIRECTORY)

    # Make sure the directory has a single slash at the end
    test_directory = os.path.join(
        os.path.normpath(os.path.join(os.getcwd(), test_name)),
        '')

    test_utils.print_info(f'Running {test_name}...')

    if os.path.isfile(f'{test_directory}/expected-status'):
        with open(f'{test_directory}/expected-status', 'r') as f:
            expected_exit_status = int(f.read())
    else:
        expected_exit_status = 0

    expected_logs_file_name = f'{test_directory}/expected-logs'
    expected_output_directory = f'{test_directory}/expected-output'
    with \
            NamedTemporaryFile(
                prefix='plz-test-logs',
                dir=DATA_DIRECTORY,
                mode='wb') as logs_file, \
            TemporaryDirectory(
                prefix='plz-test-output',
                dir=DATA_DIRECTORY) as output_directory_name:
        start = datetime.datetime.now()
        test_subprocess = run_cli(
            plz_host=plz_host,
            plz_port=plz_port,
            test_name=test_name,
            app_directory=test_directory,
            actual_logs_file=logs_file,
            output_directory_name=output_directory_name)
        end = datetime.datetime.now()
        test_utils.print_info(f'Time taken: {end-start}')

        actual_exit_status = test_subprocess.returncode
        if bless:
            if actual_exit_status == expected_exit_status:
                test_utils.print_info('Blessing output...')
                test_utils.execute_command(
                    ['cp', logs_file.name, expected_logs_file_name])
                test_utils.execute_command(
                    ['rm', '-rf', expected_output_directory])
                if len(os.listdir(output_directory_name)) != 0:
                    test_utils.execute_command(
                        ['cp', '-R', output_directory_name,
                         expected_output_directory])
                test_utils.print_info('Test blessed')
            else:
                test_utils.print_error(
                    f'Was going to bless the test but it exited with status '
                    f'{actual_exit_status} (expected {actual_exit_status}')
                return False
        else:
            if actual_exit_status != expected_exit_status:
                test_utils.print_error(
                    f'Exited with a status code of {actual_exit_status}')
                test_utils.print_error(
                    f'Expected a status code of {expected_exit_status}')
                test_utils.print_error('Test failed')
                return False

            compare_logs_subp = test_utils.execute_command(
                ['git', '--no-pager', 'diff', '--no-index',
                 expected_logs_file_name,
                 logs_file.name],
                fail_on_failure=False)
            if compare_logs_subp.returncode != 0:
                test_utils.print_error(
                    'Expected logs differ from the actual ones')
                test_utils.print_error('Test failed')
                return False
            if os.path.isdir(expected_output_directory):
                compare_output_subp = test_utils.execute_command(
                    ['git',
                     '--no-pager',
                     'diff',
                     '--no-index',
                     expected_output_directory,
                     output_directory_name],
                    fail_on_failure=False)
                if compare_output_subp.returncode != 0:
                    test_utils.print_error(
                        'Expected output differ from the actual one')
                    test_utils.print_error('Test failed')
                    return False
            test_utils.print_info('Test passed')
            return True


def run_cli(
        plz_host: str,
        plz_port: int,
        test_name: str,
        app_directory: str,
        actual_logs_file: TemporaryFile,
        output_directory_name: str):
    output_directory_name = os.path.abspath(output_directory_name)
    project_name = re.sub(r'[^0-9a-zA-Z_]', '-', test_name)
    test_config_file = f'{app_directory}/test.config.json'
    suffix = re.sub(r'[^0-9a-zA-Z_]', '-',
                    '-'.join(os.path.split(test_name)[-2:]))
    cli_container = f'{CLI_CONTAINER_PREFIX}_{suffix}'
    volume = f'{VOLUME_PREFIX}{suffix}'

    if os.path.exists(test_config_file):
        with open(test_config_file, 'r') as f:
            test_args = json.load(f).get('args', [])
    else:
        test_args = []

    # Add the app directory to a Docker volume.
    test_utils.execute_command(
        ['docker', 'volume', 'create', volume],
        hide_output=True)
    test_utils.execute_command(
        ['docker',
         'run',
         f'--name={volume}',
         '--detach',
         '--interactive',
         f'--volume={volume}:/data',
         'docker:stable-git',
         '/bin/cat'],
        hide_output=False)
    test_utils.execute_command(
        ['docker',
         'container',
         'cp',
         app_directory,
         f'{volume}:/data/app'])

    # Initialize a Git repository to make excludes work.
    test_utils.execute_command(
        ['docker',
         'container',
         'run',
         '--rm',
         f'--volume={volume}:/data',
         'docker:stable-git',
         'git',
         'init',
         '--quiet',
         '/data/app'])

    # Start the CLI process.
    testp_subprocess = test_utils.execute_command(
        ['docker',
         'container',
         'run',
         f'--name={cli_container}',
         f'--detach',
         f'--network={NETWORK}',
         f'--env=PLZ_HOST={plz_host}',
         f'--env=PLZ_PORT={plz_port}',
         f'--env=PLZ_USER=plz-test',
         f'--env=PLZ_PROJECT={project_name}',
         f'--env=PLZ_INSTANCE_MARKET_TYPE=spot',
         f'--env=PLZ_MAX_BID_PRICE_IN_DOLLARS_PER_HOUR=0.5',
         f'--env=PLZ_INSTANCE_MAX_UPTIME_IN_MINUTES=0',
         f'--env=PLZ_QUIET_BUILD=true',
         f'--workdir=/data/app',
         f'--volume={volume}:/data',
         test_utils.CLI_IMAGE,
         'run',
         '--output=/data/output',
         *test_args])

    # Capture the logs and exit status
    # Pycharm has the wrong return types for Popen
    # noinspection PyTypeChecker
    test_utils.execute_command(
        ['docker',
         'container',
         'logs',
         '--follow',
         cli_container],
        substitute_stdout_lines=[
            (rb'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-'
                rb'[0-9a-f]{12}\b',
             rb'<UUID>'),
            (rb'^:: .*', rb''),
            (rb'^Instance status: .*', rb'')
        ],
        file_to_dump_stdout=actual_logs_file,
        stderr_to_stdout=True
    )

    # test_utils.execute_command(
    #     ['docker',
    #      'wait'
    #      '$cli_container'],
    #     file_to_dump_stdout=exit_status_file)
    test_utils.execute_command(
        ['docker',
         'container',
         'rm',
         cli_container],
        hide_output=True)

    # Extract the output.
    subp = test_utils.execute_command(
        ['docker',
         'container',
         'exec',
         volume,
         'sh',
         '-c',
         '[ ! -d /data/output ]'],
        fail_on_failure=False)
    if subp.returncode != 0:
        test_utils.execute_command(
            ['docker',
             'container',
             'cp',
             f'{volume}:/data/output',
             output_directory_name])
    test_utils.remove_volume(volume)

    return testp_subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('plz_host', type=str)
    parser.add_argument('plz_port', type=int)
    parser.add_argument('test_name', type=str)
    parser.add_argument('--bless', action='store_true', default=False)
    options = parser.parse_args(sys.argv[1:])
    run_test(
        options.plz_host, options.plz_port, options.test_name, options.bless)


if __name__ == '__main__':
    main()
