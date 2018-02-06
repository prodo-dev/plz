ifndef TAG
$(error "The TAG variable is unset.")
endif

ROOT = $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

include $(ROOT)/vars.mk

.PHONY: build
build:
	docker build --tag=$(TAG) .

.PHONY: push
push: build
	eval $$(aws ecr get-login --no-include-email --region $(AWS_REGION))
	docker push $(TAG)

.PHONY: tag
tag:
	@ echo $(TAG)
