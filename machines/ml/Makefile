SHELL := zsh -e -u

include ../../vars.mk

IMAGE_GROUPS = controller worker
INSTANCE_TYPES = m5.2xlarge p2.xlarge

AWS_REGION = $(shell jq -r '.aws_region' $(CONFIG_FILE))
SSH_PRIVATE_KEY_FILE = $(SECRETS_DIR)/keys/id_rsa
SSH_PUBLIC_KEY_FILE = $(SECRETS_DIR)/keys/id_rsa.pub

.PHONY: amis
amis:
	$(eval SOURCE_AMI = $(shell \
		aws --region=$(AWS_REGION) \
			ec2 describe-images \
			--owner=099720109477 \
			--filters='Name=name, Values=ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-*' \
			| jq -r '.Images | sort_by(.CreationDate) | last | .ImageId' \
	))
	$(info SOURCE_AMI = $(SOURCE_AMI))
	$(info AMI_TAG = $(AMI_TAG))
	$(foreach GROUP_AND_INSTANCE_TYPE, \
		$(join $(IMAGE_GROUPS), $(addprefix ^, $(INSTANCE_TYPES))), \
		packer build \
			-var aws-region=$(AWS_REGION) \
			-var source-ami=$(SOURCE_AMI) \
			-var group=$(word 1, $(subst ^, , $(GROUP_AND_INSTANCE_TYPE))) \
			-var instance-type=$(word 2, $(subst ^, , $(GROUP_AND_INSTANCE_TYPE))) \
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
		-var=ami_tag=$(AMI_TAG) \
		-var=ssh_public_key_file=$(SSH_PUBLIC_KEY_FILE)

.PHONY: destroy
destroy: $(SSH_PRIVATE_KEY_FILE)
	terraform destroy \
		-state=$(SECRETS_DIR)/terraform.tfstate \
		-var-file=$(CONFIG_FILE) \
		-var=ami_tag=$(AMI_TAG) \
		-var=ssh_public_key_file=$(SSH_PUBLIC_KEY_FILE)

# Necessary to make each `foreach` line a new instruction.
define \n


endef
