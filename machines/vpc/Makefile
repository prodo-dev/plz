SHELL := zsh -e -u

include ../../vars.mk

.PHONY: deploy
deploy:
	eval $$(make --file=../../vars.mk terraform); \
	terraform init; \
	terraform apply
