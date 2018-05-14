include ../../vars.mk

AWS_PROJECT = $(shell jq -r '.aws_project' $(CONFIG_FILE))
TAG = $(AWS_PROJECT)/pipenv

include ../../docker.mk
