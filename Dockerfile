FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY bot.py docker-entrypoint.sh ./
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "bot.py"]
