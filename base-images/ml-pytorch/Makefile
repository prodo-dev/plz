include ../../vars.mk

AWS_REGION = $(shell jq -r '.aws_region' $(CONFIG_FILE))
AWS_PROJECT = $(shell jq -r '.aws_project' $(CONFIG_FILE))
TAG = $(AWS_PROJECT)/ml-pytorch
CACHE_DIR = ../../cache/base-images/ml-pytorch

ANACONDA_VERSION = 5.2.0
ANACONDA_INSTALLER_SHA256 = 09f53738b0cd3bb96f5b1bac488e5528df9906be2480fe61df40e0e0d19e3d48

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
