SHELL := zsh -e -u

include ../../vars.mk

IMAGE_NAMES = controller build worker

TAG = $(shell date '+%F')

.PHONY: amis
amis:
	$(info TAG = $(TAG))
	$(foreach NAME, $(IMAGE_NAMES), \
		export AWS_SHARED_CREDENTIALS_FILE=../credentials/root.awscreds; \
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var tag=$(TAG) \
			-var group=$(NAME) \
			ami.json ${\n})

.PHONY: deploy
deploy:
	make -C ../vpc deploy
	eval $$(make --file=../../vars.mk terraform); \
	terraform init; \
	terraform apply


# Necessary to make each `foreach` line a new instruction.
define \n


endef
