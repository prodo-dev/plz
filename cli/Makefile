include ../vars.mk
include ../python.mk

check: test lint

.PHONY: test
test: environment
	pipenv run nosetests
