FROM python:3-slim

RUN mkdir -p /src
WORKDIR /src

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement=requirements.txt

COPY . ./

CMD ["python", "main.py"]
