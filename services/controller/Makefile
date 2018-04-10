SHELL := zsh -e -u

check: lint

include ../../vars.mk

AWS_PROJECT = $(shell jq -r '.aws_project' $(CONFIG_FILE))
TAG = $(AWS_PROJECT)/plz-controller

include ../../docker.mk
include ../../python.mk

ifndef TMPDIR
TMPDIR = /tmp/
endif

.PHONY: deploy
deploy: push vars-file
	$(eval HOST = $(shell terraform output -state='$(SECRETS_DIR)/terraform.tfstate' controller-host))
	../../scripts/run-ansible-playbook-on-host playbook.yml $(HOST) $(VARS_FILE)
	rm $(VARS_FILE)

.PHONY: vars-file
vars-file:
	$(eval VARS_FILE = $(shell mktemp "$(TMPDIR)ansible-vars-XXXXX"))
	jq \
		--arg image $$(docker inspect $(TAG) | jq -r '.[0].RepoDigests[0]') \
		--arg service_port 80 \
		--null-input \
		'{"image": $$image, "service_port": $$service_port}' \
		> $(VARS_FILE)
