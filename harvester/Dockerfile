FROM ubuntu
RUN apt update
RUN apt install -y curl
ENTRYPOINT /bin/bash -c 'while true; do echo Requesting harvesting; (curl -fsS -X POST $HOST:$PORT/executions/harvest > /dev/null || echo Error harvesting & ); sleep $WAIT_FOR_SECONDS; done'
