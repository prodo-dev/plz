SHELL := zsh -e -u

.PHONY: dist
dist: environment
	rm -rf build dist
	pipenv run python setup.py bdist_wheel

.PHONY: environment
environment: Pipfile.lock
	pipenv install --keep-outdated --dev

Pipfile.lock: Pipfile
	pipenv lock
