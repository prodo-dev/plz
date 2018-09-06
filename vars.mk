SHELL := zsh -e -u

ifndef SECRETS_DIR
$(error 'You must set the `SECRETS_DIR` environment variable.\nYou can use `direnv` and the .envrc file to do so.')
endif

CONFIG_FILE = $(SECRETS_DIR)/config.json

AMI_TAG = 2018-07-05

# The build timestamp is set in the secrets, and used when building the image
# for the controller and the distribution for the cli. Uses:
# - Used for the tag of the controller image
# - A file called BUILD_TIMESTAMP is created in the root source of the
#   controller in the controller image so that the controller can know its
#   version
# - The controller reports its version during ping
# - Used by the setup.py of the cli to set the version of the package
#   created
# - The cli queries the version of the package it's running as to compare
#   with the one reported by the controller
#
# There is also the file "STABLE_BUILD_TIMESTAMP". This relates only to
# "non-plz-developers" that use a prebuilt version of plz.
# The timestamp in this file should correspond to a build that is
# "stable enough". The scripts to install the cli and to start the
# controller use this timestamp as to refer to a pip package for the cli,
# and an image for the controller, that have been already built.

BUILD_TIMESTAMP = $(shell cat $(SECRETS_DIR)/BUILD_TIMESTAMP 2> /dev/null || true)

ifeq ($(BUILD_TIMESTAMP),)
    BUILD_TIMESTAMP = 0
endif

