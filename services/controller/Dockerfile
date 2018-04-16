FROM python:3-slim

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy curl openssh-client

RUN pip install pipenv

ENV TINI_VERSION v0.17.0
RUN set -ex; \
    curl -fsSL -o /tini https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini; \
    chmod +x /tini

RUN mkdir -p /src
WORKDIR /src

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY src ./src/
COPY run ./

HEALTHCHECK --interval=5s CMD curl -f http://localhost/

ENTRYPOINT ["/tini", "--", "./run"]
