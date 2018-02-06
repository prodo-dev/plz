include ../../vars.mk

TAG = $(AWS_PROJECT)/batman-controller

include ../../docker.mk
include ../../python.mk

.PHONY: deploy
deploy: push
	./deploy
