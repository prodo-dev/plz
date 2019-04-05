FROM python:3.6-slim

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy curl openssh-client

RUN pip install pipenv

ENV TINI_VERSION v0.17.0
RUN set -ex; \
    curl -fsSL -o /tini https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini; \
    chmod +x /tini


RUN curl -o aws-iam-authenticator https://amazon-eks.s3-us-west-2.amazonaws.com/1.12.7/2019-03-27/bin/linux/amd64/aws-iam-authenticator
RUN chmod +x ./aws-iam-authenticator
RUN mkdir -p /bin && cp ./aws-iam-authenticator ./bin/aws-iam-authenticator

RUN mkdir -p /src

WORKDIR /src

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY src ./src/
COPY run ./

ARG BUILD_TIMESTAMP=0

RUN echo -n $BUILD_TIMESTAMP > ./src/plz/controller/BUILD_TIMESTAMP

HEALTHCHECK --interval=5s CMD curl -f http://localhost/

ENTRYPOINT ["/tini", "--", "./run"]
