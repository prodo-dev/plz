SHELL := zsh -e -u

include ../../vars.mk

.PHONY: deploy
deploy:
	eval $$($(MAKE) --no-print-directory --file=../../vars.mk terraform); \
	terraform init; \
	terraform apply
	../scripts/run-playbook-on-host $(shell terraform output host) playbook.yml
