source ../../vars.mk

SHELL := zsh

TAG = $(PROJECT)/ml-pytorch
CACHE_DIR = ../../cache/base-images/ml-pytorch

ANACONDA_VERSION = 5.0.1
ANACONDA_INSTALLER_SHA256 = 55e4db1919f49c92d5abbf27a4be5986ae157f074bf9f8238963cd4582a4068a

.PHONY: build
build: cache
	packer build \
		-var tag=$(TAG) \
		-var cache=$(realpath $(CACHE_DIR)) \
		docker.json

.PHONY: push
push: build
	docker push $(TAG)

.PHONY: cache
cache: $(CACHE_DIR)/install/anaconda.sh $(CACHE_DIR)/pkgs

$(CACHE_DIR)/install/anaconda.sh: $(CACHE_DIR)/install
	./download \
		https://repo.continuum.io/archive/Anaconda3-$(ANACONDA_VERSION)-Linux-x86_64.sh \
		$@ \
		$(ANACONDA_INSTALLER_SHA256)
	chmod +x $@

$(CACHE_DIR)/install:
	mkdir -p $@

$(CACHE_DIR)/pkgs:
	mkdir -p $@
