SHELL := zsh -e -u

IMAGE_NAMES = controller build worker

ifndef TAG
$(error "Please specify a tag by suffixing the tag with `TAG=foo`.")
endif

.PHONY: amis
amis:
	$(foreach NAME, $(IMAGE_NAMES), packer build -var tag=$(TAG) -var group=$(NAME) ami.json${\n})


# Necessary to make each `foreach` line a new instruction.
define \n


endef
