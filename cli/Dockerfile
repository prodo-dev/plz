# Build
FROM python:3-slim

RUN mkdir -p /src
WORKDIR /src

COPY LICENSE MANIFEST.in README.rst setup.py ./
COPY src src/
RUN python setup.py bdist_wheel

# Run
FROM python:3.6

COPY --from=0 /src/dist/plz_cli-0.1.0-py3-none-any.whl /tmp/
RUN pip install /tmp/plz_cli-0.1.0-py3-none-any.whl

ENTRYPOINT ["plz"]
