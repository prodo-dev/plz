include ../../vars.mk

AWS_REGION = $(shell jq -r '.aws_region' $(CONFIG_FILE))
AWS_PROJECT = $(shell jq -r '.aws_project' $(CONFIG_FILE))
TAG = $(AWS_PROJECT)/ml-conda
CACHE_DIR = ../../cache/base-images/

ANACONDA_VERSION = 5.3.1
ANACONDA_INSTALLER_SHA256 = d4c4256a8f46173b675dd6a62d12f566ed3487f932bab6bb7058f06c124bcc27

.PHONY: build
build: cache
	packer build \
		-var tag=$(TAG) \
		-var cache=$(realpath $(CACHE_DIR)) \
		docker.json

.PHONY: push
push: build
	eval $$(aws ecr get-login --no-include-email --region $(AWS_REGION))
	docker push $(TAG)

.PHONY: cache
cache: $(CACHE_DIR)/install/anaconda.sh $(CACHE_DIR)/pkgs

$(CACHE_DIR)/install/anaconda.sh: $(CACHE_DIR)/install
	../scripts/download \
		https://repo.continuum.io/archive/Anaconda3-$(ANACONDA_VERSION)-Linux-x86_64.sh \
		$@ \
		$(ANACONDA_INSTALLER_SHA256)
	chmod +x $@

$(CACHE_DIR)/install:
	mkdir -p $@

$(CACHE_DIR)/pkgs:
	mkdir -p $@
