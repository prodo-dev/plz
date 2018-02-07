ifndef VARS_MK
VARS_MK = true

AWS_REGION = eu-west-1
AWS_AVAILABILITY_ZONE = eu-west-1a
AWS_PROJECT = 024444204267.dkr.ecr.eu-west-1.amazonaws.com

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
	@ echo 'export TF_VAR_region="$(AWS_REGION)"'
	@ echo 'export TF_VAR_availability_zone="$(AWS_AVAILABILITY_ZONE)"'
	@ echo 'export TF_VAR_project="$(AWS_PROJECT)"'

endif
