SHELL := zsh -e -u

.PHONY: check
check:
	make -C cli check
	make -C services/controller check

.PHONY: environment
environment:
	make -C cli environment
	make -C services/controller environment

.PHONY: ml-production
ml-production:
	make -C machines/ml deploy-production

.PHONY: ml-test
ml-test:
	make -C machines/ml deploy-test

.PHONY: controller-production
controller-production: ml-production
	make -C services/controller deploy-production

.PHONY: controller-test
controller-test: ml-test
	make -C services/controller deploy-test

.PHONY: deploy-production
deploy-production: ml-production controller-production

.PHONY: deploy-test
deploy-test: ml-test controller-test
