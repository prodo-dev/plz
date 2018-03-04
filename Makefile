SHELL := zsh -e -u

.PHONY: check
check:
	make -C cli check

.PHONY: vpc
vpc:
	make -C machines/vpc deploy

.PHONY: deploy-production
deploy-production: vpc
	make -C machines/ml deploy-production
	make -C services/controller deploy-production

.PHONY: deploy-test
deploy-test: vpc
	make -C machines/ml deploy-test
	make -C services/controller deploy-test
