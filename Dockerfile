FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data && chmod 777 /data

ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

CMD ["python", "-m", "wcbot"]
