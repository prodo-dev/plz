NAME = batman-visdom
TAG = prodo-ai/$(NAME)
PORT = 8097
export PORT

NETWORK = batman

.PHONY: build
build:
	docker build --tag=$(TAG) .

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
		prodo-ai/batman-visdom

.PHONY: stop
stop:
	docker stop $(NAME) || :
	docker rm $(NAME) || :
