SHELL := zsh -e -u

.PHONY: lint
lint: environment
	pipenv run flake8 src

BUILD_TIMESTAMP_FILE=src/plz/cli/BUILD_TIMESTAMP


.PHONY: dist
dist: environment
	rm -rf build dist
	echo BUILD "$(BUILD_TIMESTAMP)" > "$(BUILD_TIMESTAMP_FILE)"
	BUILD_TIMESTAMP="$(BUILD_TIMESTAMP)" pipenv run python setup.py bdist_wheel
	rm "$(BUILD_TIMESTAMP_FILE)"

.PHONY: environment
environment: .environment

.environment: Pipfile.lock
	pipenv sync --dev
	touch $@

Pipfile.lock: Pipfile
	pipenv lock
