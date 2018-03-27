SHELL := zsh -e -u

ifndef VARS_MK
VARS_MK = true

AWS_REGION = eu-west-1
AWS_AVAILABILITY_ZONE = eu-west-1a
AWS_PROJECT = 024444204267.dkr.ecr.eu-west-1.amazonaws.com
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

.PHONY: terraform
terraform:
	@ echo 'export TF_VAR_environment="Production"'
	@ echo 'export TF_VAR_region="$(AWS_REGION)"'
	@ echo 'export TF_VAR_availability_zone="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export TF_VAR_project="$(AWS_PROJECT)"'
	@ echo 'export TF_VAR_internal_domain="$(INTERNAL_DOMAIN)"'
	@ echo 'export TF_VAR_subdomain="$(INTERNAL_DOMAIN)"'

ifdef ENVIRONMENT_NAME
.PHONY: terraform-test
terraform-test:
	@ # Given an environment named "Alice", sets the subdomain to "alice.test.inside.prodo.ai".
	@ echo 'export TF_VAR_environment="$(ENVIRONMENT_NAME)"'
	@ echo 'export TF_VAR_internal_domain="$(INTERNAL_DOMAIN)"'
	@ echo 'export TF_VAR_subdomain="$(shell echo $(ENVIRONMENT_NAME) | tr -d -C '[A-Za-z0-9_-]' | tr '[:upper:]' '[:lower:]').test.inside.$(DOMAIN)"'
else
.PHONY: terraform-test
terraform-test:
	@ echo >&2 'You must set the `ENVIRONMENT_NAME` environment variable.'
	@ echo >&2 'You can use `direnv` and the .envrc file to do so.'
	@ echo 'exit 1'
endif

endif
