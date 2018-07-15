FROM ubuntu
RUN apt update
RUN apt install -y curl
ENTRYPOINT /bin/bash -c 'while true; do ( curl -X POST $HOST:$PORT/executions/harvest & ) ; sleep $WAIT_FOR_SECONDS; done'
