FROM python:3-slim

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy openssh-client

RUN pip install pipenv

RUN mkdir -p /src
WORKDIR /src

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY src ./src/

ENV PYTHONPATH ./src
CMD ["python", "./src/plz/controller/main.py"]
