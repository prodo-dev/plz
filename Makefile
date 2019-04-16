SHELL := zsh -e -u

include vars.mk

.PHONY: check
check: environment
	pipenv run yapf -rd .
	$(MAKE) -C cli check
	$(MAKE) -C services/controller check
	BUILD_TIMESTAMP=$(BUILD_TIMESTAMP) python3 test/run.py
	terraform fmt -check

.PHONY: format
format: environment
	pipenv run yapf -ri .

.PHONY: environment
environment: Pipfile.lock
	pipenv sync --dev
	touch $@
	$(MAKE) -C cli environment
	$(MAKE) -C services/controller environment

.PHONY: ml
ml:
	$(MAKE) -C machines/ml deploy

.PHONY: controller
controller: ml
	$(MAKE) -C services/controller deploy

.PHONY: deploy
deploy: ml controller

Pipfile.lock: Pipfile
	pipenv lock


.PHONY: destroy
destroy: ml-destroy

.PHONY: ml-destroy
ml-destroy:
	$(MAKE) -C machines/ml destroy
