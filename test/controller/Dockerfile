# Build
FROM python:3.6-slim

RUN mkdir -p /services/controller/src
RUN mkdir -p /cli/src
RUN mkdir -p /controller_tests/src
WORKDIR /cli

RUN pip install pipenv

COPY cli/README.rst cli/setup.py cli/Pipfile cli/Pipfile.lock ./

COPY cli/src /cli/src/
COPY services/controller/src /services/controller/src/
COPY test/controller/src /controller_tests/src/
COPY test/end-to-end /end-to-end/

RUN pipenv sync --dev

ENTRYPOINT pipenv run nosetests /controller_tests/ --nocapture -v
