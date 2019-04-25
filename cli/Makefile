include ../vars.mk
include ../python.mk

check: test lint

.PHONY: test
test: environment
	COVERAGE_FILE=../test/coverage/results/cli_nose_tests.coverage pipenv run coverage run --source=. -m nose
