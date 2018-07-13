SHELL := zsh -e -u

ifndef SECRETS_DIR
$(error 'You must set the `SECRETS_DIR` environment variable.\nYou can use `direnv` and the .envrc file to do so.')
endif

CONFIG_FILE = $(SECRETS_DIR)/config.json

AMI_TAG = 2018-07-05

BUILD_TIMESTAMP = `date +%y%m%d%H%M%S`
