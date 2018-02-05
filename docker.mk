ifndef TAG
$(error "The TAG variable is unset.")
endif

.PHONY: build
build:
	docker build --tag=$(TAG) .

.PHONY: push
push: build
	docker push $(TAG)
