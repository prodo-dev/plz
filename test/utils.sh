#!/usr/bin/env zsh

PROJECT_NAME=plztest
NETWORK="${NETWORK:-${PROJECT_NAME}_default}"
VOLUME_PREFIX="${PROJECT_NAME}_data_"
CLI_BUILDER_IMAGE="${PROJECT_NAME}/cli-builder"
CLI_IMAGE="${PROJECT_NAME}/cli"
CLI_CONTAINER_PREFIX="${PROJECT_NAME}_cli_"
CONTROLLER_IMAGE="${PROJECT_NAME}/controller"
CONTROLLER_CONTAINER="${PROJECT_NAME}_controller_1"
# Controller hostname as set by docker compose. For each a host, the
# network includes the service name as well as the container name.
# It's useful to remember that we can also use the service name, as
# the container name, by default, includes a random string. The
# controller just uses "redis" (instead of the redis container name)
# when referring to the redis host for the same reason
CONTROLLER_HOSTNAME="controller"
CONTROLLER_TESTS_IMAGE="${PROJECT_NAME}/controller-tests"
CONTROLLER_TESTS_CONTAINER="${PROJECT_NAME}_controller-tests_1"
CONTROLLER_PORT=80

TEST_DIRECTORY=${0:a:h}
DATA_DIRECTORY="${PWD}/test_cache/"

autoload -U colors && colors

if [[ -t 1 ]]; then
  function info {
    echo "${fg[green]}>${reset_color} $@"
  }
  function warning {
    echo "${fg[yellow]}>${reset_color} $@"
  }
  function error {
    echo "${fg[red]}>${reset_color} $@"
  }
else
  function info {
    echo > $@
  }
  function warning {
    echo > $@
  }
  function error {
    echo > $@
  }
fi

function remove_volume {
  if container_exists $1; then
    docker container kill $1 >& /dev/null || :
    docker container rm $1 > /dev/null
  fi
  if volume_exists $1; then
    docker volume rm $1 > /dev/null
  fi
}

function container_exists {
  docker container inspect $1 >& /dev/null
}

function volume_exists {
  docker volume inspect $1 >& /dev/null
}
