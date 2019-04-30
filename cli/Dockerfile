# Build
FROM python:3.6-slim as builder

RUN mkdir -p /services/controller/src
RUN mkdir -p /cli/src
WORKDIR /cli

COPY cli/LICENSE cli/MANIFEST.in cli/README.rst cli/setup.py ./
COPY cli/src /cli/src/
COPY services/controller/src /services/controller/src/
RUN python setup.py bdist_wheel

# Run
FROM python:3.6

COPY --from=builder /cli/dist/plz_cli-0.1.0-py3-none-any.whl /tmp/
RUN pip install --find-links /tmp/ plz_cli[test]

ENV PYTHONUNBUFFERED 1
ENTRYPOINT ["plz"]
