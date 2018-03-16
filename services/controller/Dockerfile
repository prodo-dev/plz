FROM python:3-slim

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy openssh-client

RUN mkdir -p /src
WORKDIR /src

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement=requirements.txt

COPY src ./src/

ENV PYTHONPATH ./src
CMD ["python", "./src/batman/controller/main.py"]
