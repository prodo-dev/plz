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
	IMAGE=$$(docker inspect $(TAG) | jq -r '.[0].RepoDigests[0]'); \
	SERVICE_PORT=80; \
	echo "image: \"$${IMAGE}\"" >> $(VARS_FILE); \
	echo "service_port: \"$${SERVICE_PORT}\"" >> $(VARS_FILE)
