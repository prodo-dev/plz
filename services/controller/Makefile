SHELL := zsh -e -u

include ../../vars.mk

TAG = $(AWS_PROJECT)/plz-controller

include ../../docker.mk
include ../../python.mk

.PHONY: deploy-production
deploy-production: push
	./deploy production.tfstate

.PHONY: deploy-test
deploy-test: push
	./deploy test.tfstate
