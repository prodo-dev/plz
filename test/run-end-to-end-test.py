#!/usr/bin/env zsh
import json
import os
import re

import test_utils

# cd ${0:a:h:h}
#
# source ./test/utils.sh

# def run_test(test_name: str):
#   # local test_name test_directory
#   # local expected_exit_status actual_exit_status_file actual_exit_status
#   # local expected_logs actual_logs
#   # local expected_output_directory actual_output_directory
#   # local start end
#
#   test_directory="${PWD}/test/${test_name}"
#
#   echo
#   info "Running ${test_name}..."
#
#   if [[ -f "${test_directory}/expected-status" ]]; then
#     expected_exit_status=$(cat "${test_directory}/expected-status")
#   else
#     expected_exit_status=0
#   fi
#   actual_exit_status_file=$(mktemp "${DATA_DIRECTORY}/plz-test-status.XXXXX")
#   expected_logs="${test_directory}/expected-logs"
#   actual_logs=$(mktemp "${DATA_DIRECTORY}/plz-test-logs.XXXXX")
#   expected_output_directory="${test_directory}/expected-output"
#   actual_output_directory=$(mktemp "${DATA_DIRECTORY}/plz-test-output.XXXXX")
#   rm $actual_output_directory # It's been created as a file.
#
#   start=$(date +%s)
#   run_cli $test_name $test_directory $actual_exit_status_file $actual_logs $actual_output_directory
#   end=$(date +%s)
#
#   info "Time taken: $((end - start))s."
#
#   actual_exit_status=$(cat $actual_exit_status_file)
#   if $bless; then
#     if [[ $actual_exit_status -eq $expected_exit_status ]]; then
#       info 'Blessing output...'
#       cp $actual_logs $expected_logs
#       rm -rf $expected_output_directory
#       if [[ -e $actual_output_directory ]]; then
#         cp -R $actual_output_directory $expected_output_directory
#       fi
#       info 'Test blessed.'
#     else
#       error "Exited with a status code of ${actual_exit_status}."
#       return 1
#     fi
#   else
#     if [[ $actual_exit_status -ne $expected_exit_status ]]; then
#       error "Exited with a status code of ${actual_exit_status}."
#       error "Expected a status code of ${expected_exit_status}."
#       error 'Test failed.'
#       return 1
#     else
#       info 'Comparing output...'
#       if git --no-pager diff --no-index $expected_logs $actual_logs && \
#          ( ! [[ -e $expected_output_directory ]] || \
#            git --no-pager diff --no-index $expected_output_directory $actual_output_directory ); then
#         info 'Test passed.'
#       else
#         error 'Test failed.'
#         return 1
#       fi
#     fi
#   fi
# }
from test_utils import CLI_CONTAINER_PREFIX, VOLUME_PREFIX


def run_cli(
        test_name: str, app_directory: str, exit_status_file: str,
        logs_file: str,
        output_directory: str):
    # local test_name app_directory exit_status_file logs_file output_directory
    # local project_name test_config_file suffix cli_container volume test_args
    exit_status_file = os.path.abspath(exit_status_file)
    logs_file = os.path.abspath(logs_file)
    output_directory = os.path.abspath(output_directory)
    project_name = re.sub(r'[^0-9a-zA-Z_]', '-', test_name)
    test_config_file = f'{app_directory}/test.config.json'
    suffix = re.sub(r'[^0-9a-zA-Z_]', '-',
                    '-'.join(os.path.split(app_directory)[-2:]))
    cli_container = f'{CLI_CONTAINER_PREFIX}_{suffix}'
    volume = f'{VOLUME_PREFIX}_${suffix}'

    if os.path.exists(test_config_file):
        with open(test_config_file, 'r') as f:
            test_args = json.load(f).get('args', [])

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
        hide_output=True)
    test_utils.execute_command(
        ['docker',
         'container',
         'cp',
         app_directory,
         f'{volume}/data/app'])

    # Initialize a Git repository to make excludes work.

    docker container run \
        --rm \
        --volume=$volume:/data \
        docker:stable-git \
    git init --quiet /data/app

  # Start the CLI process.
  docker container run \
      --name=$cli_container \
      --detach \
      --network=$NETWORK \
      --env=PLZ_HOST=$PLZ_HOST \
      --env=PLZ_PORT=$PLZ_PORT \
      --env=PLZ_USER='plz-test' \
      --env=PLZ_PROJECT=$project_name \
      --env=PLZ_INSTANCE_MARKET_TYPE=spot \
      --env=PLZ_MAX_BID_PRICE_IN_DOLLARS_PER_HOUR=0.5 \
      --env=PLZ_INSTANCE_MAX_UPTIME_IN_MINUTES=0 \
      --env=PLZ_QUIET_BUILD=true \
      --workdir=/data/app \
      --volume="${volume}:/data" \
    $CLI_IMAGE \
    run --output=/data/output $test_args \
    > /dev/null

  # Capture the logs and exit status.
  docker container logs --follow $cli_container \
    |& redact_uuids \
    |& redact_debug_messages \
    |& redact_instance_status \
    | tee $logs_file
  docker wait $cli_container > $exit_status_file
  docker container rm $cli_container > /dev/null

  # Extract the output.
  docker container exec $volume sh -c '[ ! -d /data/output ]' \
    || docker container cp $volume:/data/output $output_directory
  test_utils.remove_volume(volume)
}

function redact_uuids {
  # The "$| = 1" bit disables buffering so we get output as we need it.
  perl -pe '$| = 1; s/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/<UUID>/g'
}

function redact_debug_messages {
  grep -v '^:: '
}

function redact_instance_status {
  grep -v '^Instance status: '
}

# In "bless mode", instead of comparing the actual output against expected
# output, we save the output.
bless=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --bless)
      bless=true
      shift ;;
    *)
      break
  esac
done

run_test $@
