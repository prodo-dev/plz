#!/usr/bin/env bash

set -e
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null && pwd)"

SECRETS_DIR=$PWD/aws_config \
  BUILD_TIMESTAMP="$(cat ${DIR}/../STABLE_BUILD_TIMESTAMP)" \
  LOG_LEVEL="${LOG_LEVEL:-DEBUG}" \
  CACHE_DIR="${CACHE_DIR:-${DIR}/../dev_cache/}" \
  docker-compose --project-name=plz --file="${DIR}/development-aws-k8s.yml" up --build "$@"
