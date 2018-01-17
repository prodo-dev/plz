FROM python:3

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN pip install visdom
RUN python -c 'import visdom.server; visdom.server.download_scripts()'

ENTRYPOINT ["python", "-m", "visdom.server"]
