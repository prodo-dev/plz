SHELL := zsh -e -u

IMAGE_NAMES = controller build worker

.PHONY: amis
amis:
	$(foreach NAME, $(IMAGE_NAMES), packer build -var group=$(NAME) ami.json${\n})


# Necessary to make each `foreach` line a new instruction.
define \n


endef
