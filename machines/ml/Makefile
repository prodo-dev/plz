SHELL := zsh -e -u

include ../../vars.mk

IMAGE_GROUPS = controller worker

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
	$(info AMI_TAG = $(AMI_TAG))
	$(foreach GROUP, $(IMAGE_GROUPS), \
		export AWS_SHARED_CREDENTIALS_FILE=../credentials/root.awscreds; \
		export AWS_PROFILE=; \
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var source-ami=$(SOURCE_AMI) \
			-var group=$(GROUP) \
			-var ami-tag=$(AMI_TAG) \
			ami.json ${\n})

.PHONY: deploy-production
deploy-production:
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform-production); \
	terraform init; \
	terraform apply -state=production.tfstate

.PHONY: deploy-test
deploy-test:
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform-test); \
	terraform init; \
	terraform apply -state=test.tfstate


# Necessary to make each `foreach` line a new instruction.
define \n


endef
