SHELL := zsh -e -u

.PHONY: lint
lint: environment
	pipenv run yapf -rd src/

.PHONY: format
format: environment
	pipenv run yapf -ri src/

.PHONY: dist
dist: environment
ifeq ($(BUILD_TIMESTAMP),)
	$(error "BUILD_TIMESTAMP is unset")
endif
	rm -rf build dist
	BUILD_TIMESTAMP=$(BUILD_TIMESTAMP) pipenv run python setup.py bdist_wheel

.PHONY: environment
environment: .environment

.environment: Pipfile.lock
	pipenv sync --dev
	touch $@

Pipfile.lock: Pipfile
	pipenv lock
