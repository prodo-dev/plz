FROM python:3

RUN pip install pipenv

WORKDIR /src
ONBUILD COPY Pipfile Pipfile.lock ./
ONBUILD RUN pipenv install --system --deploy
