SHELL := zsh -e -u

IMAGE_NAMES = controller build worker

.PHONY: amis
amis:
	@ [[ -z "$(TAG)" ]] && { \
		echo >&2 'Please specify a tag by suffixing the tag with `TAG=foo`.'; \
		exit 1; \
	}
	$(foreach NAME, $(IMAGE_NAMES), packer build -var tag=$(TAG) -var group=$(NAME) ami.json${\n})

.PHONY: deploy
deploy:
	eval $$(make --file=../../vars.mk terraform); \
	terraform init; \
	terraform apply


# Necessary to make each `foreach` line a new instruction.
define \n


endef
