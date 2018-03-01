SHELL := zsh -e -u

include ../../vars.mk

IMAGE_NAMES = build worker

TAG = $(shell date '+%F')

.PHONY: amis
amis:
	$(info TAG = $(TAG))
	$(foreach NAME, $(IMAGE_NAMES), \
		export AWS_SHARED_CREDENTIALS_FILE=../credentials/root.awscreds; \
		export AWS_PROFILE=; \
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var tag=$(TAG) \
			-var group=$(NAME) \
			ami.json ${\n})

.PHONY: deploy-production
deploy-production:
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform); \
	terraform init; \
	terraform apply -state=production.tfstate

.PHONY: deploy-test
deploy-test:
	$(MAKE) --no-print-directory --file=../../vars.mk terraform
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform); \
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform-test); \
	terraform init; \
	terraform apply -state=test.tfstate


# Necessary to make each `foreach` line a new instruction.
define \n


endef
