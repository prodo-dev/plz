SHELL := zsh

include ../../vars.mk

NAME = plz-visdom
TAG = $(AWS_PROJECT)/visdom

NETWORK = plz
PORT = 8097
export PORT

include ../../docker.mk

.PHONY: start
start: build
	@ [[ -n "$(VOLUME)" ]] || echo >&2 '\nWARNING: no data volume specified. I recommend setting `VOLUME`.'
	docker run \
		--name="$(NAME)" \
		--detach \
		--net="$(NETWORK)" \
		--publish="$${PORT:-8097}:8097" \
		$$([[ -n "$(VOLUME)" ]] && echo "--volume=$(VOLUME):/root/.visdom" || :) \
		--init \
		$(TAG)

.PHONY: stop
stop:
	docker stop $(NAME) || :
	docker rm $(NAME) || :
