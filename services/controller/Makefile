SHELL := zsh -e -u

check: lint

include ../../vars.mk

AWS_PROJECT = $(shell jq -r '.aws_project' $(CONFIG_FILE))
PUBLIC_REPOSITORY = $(shell jq -r 'if .public_repository then .public_repository else "" end' $(CONFIG_FILE))
TAG = $(AWS_PROJECT)/plz-controller

include ../../docker.mk
include ../../python.mk

ifndef TMPDIR
TMPDIR = /tmp/
endif

.PHONY: deploy
deploy: push vars-file maybe-deploy-public
	$(eval HOST = $(shell terraform output -state='$(SECRETS_DIR)/terraform.tfstate' controller-host-public-ip))
	../../scripts/run-ansible-playbook-on-host playbook.yml $(HOST) $(VARS_FILE)
	rm $(VARS_FILE)

.PHONY: maybe-deploy-public
maybe-deploy-public: build
ifneq ($(PUBLIC_REPOSITORY),)
	docker tag $(TAG) "$(PUBLIC_REPOSITORY):timestamp_$(BUILD_TIMESTAMP)"
	docker push "$(PUBLIC_REPOSITORY):timestamp_$(BUILD_TIMESTAMP)"
endif

.PHONY: vars-file
vars-file:
	$(eval VARS_FILE = $(shell mktemp "$(TMPDIR)ansible-vars-XXXXX"))
	jq \
		--arg image $$(docker inspect $(TAG) | jq -r '.[0].RepoDigests[0]') \
		--arg service_port 80 \
		--arg aws_worker_ami plz-worker-$(AMI_TAG) \
		--null-input \
		'{"image": $$image, "service_port": $$service_port, "aws_worker_ami": $$aws_worker_ami}' \
		> $(VARS_FILE)
