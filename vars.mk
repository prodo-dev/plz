SHELL := zsh -e -u

ifndef VARS_MK
VARS_MK = true

ifndef ENVIRONMENT_NAME
$(error 'You must set the `ENVIRONMENT_NAME` environment variable.\nYou can use `direnv` and the .envrc file to do so.')
endif

AWS_REGION = eu-west-1
AWS_AVAILABILITY_ZONE = eu-west-1a
AWS_PROJECT = 024444204267.dkr.ecr.eu-west-1.amazonaws.com
AMI_TAG = 2018-03-27
KEY_NAME = plz-$(shell tr '[:upper:]' '[:lower:]' <<< $(ENVIRONMENT_NAME))-key
DOMAIN = prodo.ai
INTERNAL_DOMAIN = inside.$(DOMAIN)

.PHONY: no-op
no-op:
	true

.PHONY: bash
bash:
	@ echo 'export AWS_REGION="$(AWS_REGION)"'
	@ echo 'export AWS_AVAILABILITY_ZONE="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export AWS_PROJECT="$(AWS_PROJECT)"'
	@ echo 'export AWS_WORKER_AMI="plz-worker-$(AMI_TAG)"'
	@ echo 'export AWS_KEY_NAME="$(KEY_NAME)"'

.PHONY: terraform
terraform:
	@ echo 'export TF_VAR_environment="Production"'
	@ echo 'export TF_VAR_region="$(AWS_REGION)"'
	@ echo 'export TF_VAR_availability_zone="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export TF_VAR_project="$(AWS_PROJECT)"'
	@ echo 'export TF_VAR_ami_tag="$(AMI_TAG)"'
	@ echo 'export TF_VAR_key_name="$(KEY_NAME)"'
	@ echo 'export TF_VAR_internal_domain="$(INTERNAL_DOMAIN)"'
	@ echo 'export TF_VAR_subdomain="$(INTERNAL_DOMAIN)"'

.PHONY: terraform-test
terraform-test:
	@ # Given an environment named "Alice", sets the subdomain to "alice.test.inside.prodo.ai".
	@ echo 'export TF_VAR_environment="$(ENVIRONMENT_NAME)"'
	@ echo 'export TF_VAR_internal_domain="$(INTERNAL_DOMAIN)"'
	@ echo 'export TF_VAR_subdomain="$(shell echo $(ENVIRONMENT_NAME) | tr -d -C '[A-Za-z0-9_-]' | tr '[:upper:]' '[:lower:]').test.inside.$(DOMAIN)"'

endif
