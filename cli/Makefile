check: test lint

include ../vars.mk
include ../python.mk

.PHONY: test
test: environment
	pipenv run nosetests
