SHELL := zsh -e -u

ifndef VARS_MK
VARS_MK = true

AWS_REGION = eu-west-1
AWS_AVAILABILITY_ZONE = eu-west-1a
AWS_PROJECT = 024444204267.dkr.ecr.eu-west-1.amazonaws.com
DOMAIN = prodo.ai
SUBDOMAIN = inside.prodo.ai

.PHONY: no-op
no-op:
	true

.PHONY: bash
bash:
	@ echo 'export AWS_REGION="$(AWS_REGION)"'
	@ echo 'export AWS_AVAILABILITY_ZONE="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export AWS_PROJECT="$(AWS_PROJECT)"'
	@ echo 'export DOMAIN="$(DOMAIN)"'
	@ echo 'export SUBDOMAIN="$(SUBDOMAIN)"'

.PHONY: terraform
terraform:
	@ echo 'export TF_VAR_region="$(AWS_REGION)"'
	@ echo 'export TF_VAR_availability_zone="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export TF_VAR_project="$(AWS_PROJECT)"'
	@ echo 'export TF_VAR_domain="$(DOMAIN)"'
	@ echo 'export TF_VAR_subdomain="$(SUBDOMAIN)"'

.PHONY: terraform-test
terraform-test:
	@ if [[ -z "$$ENVIRONMENT_NAME" ]]; then \
		echo >&2 'You must set the `ENVIRONMENT_NAME` environment variable.'; \
		echo >&2 'You can use `direnv` and the .envrc file to do so.'; \
		echo 'exit 1'; \
	else \
		echo 'export TF_VAR_environment="$$ENVIRONMENT_NAME"'; \
	fi

.PHONY: domain
print-domain:
	@ echo $(DOMAIN)

.PHONY: subdomain
print-subdomain:
	@ echo $(SUBDOMAIN)

endif
