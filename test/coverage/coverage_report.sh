#!/bin/bash

if command -v realpath > /dev/null; then
  DIR_OF_THIS_SCRIPT="$(cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")" && pwd)"
else
  DIR_OF_THIS_SCRIPT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
fi


RESULTS_DIR="${DIR_OF_THIS_SCRIPT}/results"
RCFILE="${DIR_OF_THIS_SCRIPT}/coveragerc"

# Use a new shell to cd to the plz root path. Otherwise the script would
# depend on pwd, as the paths in the rcfile are constant
( \
  cd "$DIR_OF_THIS_SCRIPT"/../.. && \
  COVERAGE_FILE="${RESULTS_DIR}/total.coverage" coverage combine \
    --rcfile="${RCFILE}" "${RESULTS_DIR}"/*.coverage;
  COVERAGE_FILE="${RESULTS_DIR}/total.coverage" coverage report | sed "s:`pwd`::"
)

