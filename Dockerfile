FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y gnucobol4 build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml .
RUN pip install --upgrade pip && pip install pytest anthropic

COPY . .

CMD ["pytest", "test_bench.py", "-v"]