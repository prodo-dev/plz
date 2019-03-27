FROM python:3-slim

WORKDIR /src
COPY . ./
CMD ./main.py
