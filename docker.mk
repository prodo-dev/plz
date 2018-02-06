ifndef TAG
$(error "The TAG variable is unset.")
endif

.PHONY: build
build:
	docker build --tag=$(TAG) .

.PHONY: push
push: build
	eval $$(aws ecr get-login --no-include-email --region eu-west-1)
	docker push $(TAG)

.PHONY: tag
tag:
	@ echo $(TAG)
