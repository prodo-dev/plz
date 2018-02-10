include ../../vars.mk

TAG = $(AWS_PROJECT)/batman-controller

include ../../docker.mk
include ../../python.mk

.PHONY: deploy-production
deploy-production: push
	./deploy terraform.tfstate

.PHONY: deploy-test
deploy-test: push
	./deploy test.tfstate
