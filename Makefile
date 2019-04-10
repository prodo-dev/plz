SHELL := zsh -e -u

include vars.mk

.PHONY: check
check:
	$(MAKE) -C cli check
	$(MAKE) -C services/controller check
	BUILD_TIMESTAMP=$(BUILD_TIMESTAMP) python3 test/run.py
	terraform fmt -check

.PHONY: environment
environment:
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

.PHONY: destroy
destroy: ml-destroy


.PHONY: ml-destroy
ml-destroy:
	$(MAKE) -C machines/ml destroy
