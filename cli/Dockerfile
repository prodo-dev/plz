# Build
FROM python:3-slim

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy make

RUN pip install pipenv

RUN mkdir -p /src
WORKDIR /src

COPY Pipfile Pipfile.lock ./
RUN pipenv install --system --deploy

COPY LICENSE MANIFEST.in README.rst setup.py ./
COPY src src/
RUN python setup.py bdist_wheel

# Run
FROM python:3.6

COPY --from=0 /src/dist/plz_cli-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/plz_cli-0.1.0-py3-none-any.whl

ENTRYPOINT ["plz"]
