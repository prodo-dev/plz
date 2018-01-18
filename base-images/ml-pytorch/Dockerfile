FROM nvidia/cuda:9.0-cudnn7-runtime-ubuntu16.04

RUN set -ex; \
    apt-get update -qq; \
    apt-get upgrade -qqy

RUN apt-get install -qqy bzip2 curl g++

ENV ANACONDA_VERSION 5.0.1

RUN set -ex; \
    curl -fsSL -o /tmp/anaconda.sh "https://repo.continuum.io/archive/Anaconda3-${ANACONDA_VERSION}-$(uname -s)-$(uname -p).sh"; \
    chmod +x /tmp/anaconda.sh; \
    /tmp/anaconda.sh -b -p /opt/anaconda; \
    rm /tmp/anaconda.sh

ENV PATH /opt/anaconda/envs/default/bin:/opt/anaconda/bin:${PATH}

WORKDIR /env
COPY environment.yml ./
RUN conda env create --name=default

WORKDIR /src
ONBUILD COPY environment.yml ./
ONBUILD RUN conda env update --name=default
ONBUILD COPY . ./
