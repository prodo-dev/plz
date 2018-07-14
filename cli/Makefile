check: test lint

include ../python.mk

.PHONY: test
test: environment
	pipenv run nosetests
