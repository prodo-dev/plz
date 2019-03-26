FROM python:3-slim

# This dir exists in the image
WORKDIR /src
COPY . ./
CMD ./main.py
