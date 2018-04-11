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

COPY run ./
COPY src ./src/

HEALTHCHECK CMD curl -f http://localhost/

ENTRYPOINT ["/tini", "--", "./run"]
