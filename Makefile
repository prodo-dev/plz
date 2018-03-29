SHELL := zsh -e -u

.PHONY: check
check:
	$(MAKE) -C cli check
	$(MAKE) -C services/controller check

.PHONY: environment
environment:
	$(MAKE) -C cli environment
	$(MAKE) -C services/controller environment

.PHONY: ml-production
ml-production:
	$(MAKE) -C machines/ml deploy-production

.PHONY: ml-test
ml-test:
	$(MAKE) -C machines/ml deploy-test

.PHONY: controller-production
controller-production: ml-production
	$(MAKE) -C services/controller deploy-production

.PHONY: controller-test
controller-test: ml-test
	$(MAKE) -C services/controller deploy-test

.PHONY: deploy-production
deploy-production: ml-production controller-production

.PHONY: deploy-test
deploy-test: ml-test controller-test
