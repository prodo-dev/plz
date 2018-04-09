SHELL := zsh -e -u

include ../../vars.mk

IMAGE_GROUPS = controller worker

AWS_REGION = $(shell jq -r '.aws_region' $(CONFIG_FILE))
AMI_TAG = $(shell jq -r '.ami_tag' $(CONFIG_FILE))
SSH_PRIVATE_KEY_FILE = $(SECRETS_DIR)/keys/plz
SSH_PUBLIC_KEY_FILE = $(SECRETS_DIR)/keys/plz.pub

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
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var source-ami=$(SOURCE_AMI) \
			-var group=$(GROUP) \
			-var ami-tag=$(AMI_TAG) \
			ami.json ${\n})

$(SSH_PRIVATE_KEY_FILE):
	mkdir -p $(shell dirname $@)
	ssh-keygen -N '' -f $@

.PHONY: deploy
deploy: $(SSH_PRIVATE_KEY_FILE)
	terraform init
	terraform apply \
		-state=$(SECRETS_DIR)/terraform.tfstate \
		-var-file=$(CONFIG_FILE) \
		-var=ssh_public_key_file=$(SSH_PUBLIC_KEY_FILE)


# Necessary to make each `foreach` line a new instruction.
define \n


endef
