ifndef TAG
$(error "The TAG variable is unset.")
endif

ROOT = $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

include $(ROOT)/vars.mk

AWS_REGION = $(shell jq -r '.aws_region' $(CONFIG_FILE))

.PHONY: build
build:
ifeq ($(BUILD_TIMESTAMP),)
	$(error "The BUILD_TIMESTAMP variable is unset")
endif
	docker build --tag=$(TAG) --build-arg BUILD_TIMESTAMP=$(BUILD_TIMESTAMP) .

.PHONY: push
push: build
	eval $$(aws ecr get-login --no-include-email --region $(AWS_REGION))
	docker push $(TAG)

.PHONY: tag
tag:
	@ echo $(TAG)
