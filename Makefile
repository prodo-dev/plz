SHELL := zsh -e -u

.PHONY: check
check:
	make -C cli check

.PHONY: vpc
vpc:
	make -C machines/vpc deploy

.PHONY: vpn
vpn: vpc
	make -C machines/vpn deploy

.PHONY: ml-production
ml-production: vpc
	make -C machines/ml deploy-production

.PHONY: ml-test
ml-test: vpc
	make -C machines/ml deploy-test

.PHONY: dns
dns: vpc vpn ml-production
	make -C machines/dns deploy

.PHONY: controller-production
controller-production: vpc ml-production
	make -C services/controller deploy-production

.PHONY: controller-test
controller-test: vpc ml-test
	make -C services/controller deploy-test

.PHONY: deploy-production
deploy-production: vpc vpn ml-production controller-production dns

.PHONY: deploy-test
deploy-test: vpc ml-test controller-test
