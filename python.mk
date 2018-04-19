SHELL := zsh -e -u

.PHONY: test
test: environment
	pipenv run nosetests

.PHONY: lint
lint: environment
	pipenv run flake8 src

.PHONY: dist
dist: environment
	rm -rf build dist
	pipenv run python setup.py bdist_wheel

.PHONY: environment
environment: .environment

.environment: Pipfile.lock
	pipenv install --keep-outdated --dev
	touch $@

Pipfile.lock: Pipfile
	pipenv lock
