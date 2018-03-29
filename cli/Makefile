check: test lint

include ../python.mk

.PHONY: test
test: environment
	pipenv run nosetests

.PHONY: lint
lint: environment
	pipenv run flake8 src/**/*.py
