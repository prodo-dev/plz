SHELL := zsh -e -u

include ../../vars.mk

IMAGE_NAMES = controller worker

TAG = $(shell date '+%F')

.PHONY: amis
amis:
	$(eval SOURCE_AMI = $(shell \
		aws --region=$(AWS_REGION) \
			ec2 describe-images \
			--owner=099720109477 \
			--filters='Name=name, Values=ubuntu/images/hvm-ssd/ubuntu-xenial-16.04-amd64-server-*' \
			| jq -r '.Images | sort_by(.CreationDate) | last | .ImageId' \
	))
	$(info SOURCE_AMI = $(SOURCE_AMI))
	$(info TAG = $(TAG))
	$(foreach NAME, $(IMAGE_NAMES), \
		export AWS_SHARED_CREDENTIALS_FILE=../credentials/root.awscreds; \
		export AWS_PROFILE=; \
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var source-ami=$(SOURCE_AMI) \
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
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform); \
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform-test); \
	terraform init; \
	terraform apply -state=test.tfstate


# Necessary to make each `foreach` line a new instruction.
define \n


endef
