SHELL := zsh -e -u

include ../../vars.mk

TAG = $(AWS_PROJECT)/plz-controller

include ../../docker.mk
include ../../python.mk

ifndef TMPDIR
TMPDIR = /tmp/
endif

.PHONY: deploy-production
deploy-production: push vars-file
	$(eval HOST = $(shell terraform output -state='../../machines/ml/production.tfstate' controller-host))
	../../scripts/run-ansible-playbook-on-host playbook.yml $(HOST) $(VARS_FILE)
	rm $(VARS_FILE)

.PHONY: deploy-test
deploy-test: push vars-file
	$(eval HOST = $(shell terraform output -state='../../machines/ml/test.tfstate' controller-host))
	../../scripts/run-ansible-playbook-on-host playbook.yml $(HOST) $(VARS_FILE)
	rm $(VARS_FILE)

.PHONY: vars-file
vars-file:
	$(eval VARS_FILE = $(shell mktemp "$(TMPDIR)ansible-vars-XXXXX"))
	jq \
		--arg image $$(docker inspect $(TAG) | jq -r '.[0].RepoDigests[0]') \
		--arg service_port 80 \
		--arg aws_worker_ami "$(AWS_WORKER_AMI)" \
		--arg aws_key_name "$(KEY_NAME)" \
		--null-input \
		'{"image": $$image, "service_port": $$service_port, "aws_worker_ami": $$aws_worker_ami, "aws_key_name", $$aws_key_name}' \
		> $(VARS_FILE)
