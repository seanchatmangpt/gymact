FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends tmux bash \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir pytest==8.3.3

RUN mkdir -p /logs /agent-logs

WORKDIR /app

CMD ["sleep", "infinity"]
