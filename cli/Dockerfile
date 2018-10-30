# Build
FROM python:3.6-slim as builder

RUN mkdir -p /services/controller/src
RUN mkdir -p /cli/src
WORKDIR /cli

# Pipenv is needed because we use this image to run the controller tests,
# as we need the code for plz configuration, controller proxying,
# etc.
RUN pip install pipenv

COPY cli/LICENSE cli/MANIFEST.in cli/README.rst cli/setup.py cli/Pipfile cli/Pipfile.lock ./

COPY cli/src /cli/src/
COPY services/controller/src /services/controller/src/
RUN python setup.py bdist_wheel
RUN pipenv install
RUN pipenv install nose

# Run
FROM python:3.6

COPY --from=builder /cli/dist/plz_cli-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/plz_cli-0.1.0-py3-none-any.whl

ENV PYTHONUNBUFFERED 1
ENTRYPOINT ["plz"]
