FROM python:3.12-slim

# Install ffmpeg for audio playback
RUN apt-get update && \
    apt-get install -y ffmpeg git curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy bot and requirements
COPY bot.py requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Ensure yt-dlp is installed as latest version
RUN pip install --no-cache-dir --upgrade yt-dlp

# Run bot
CMD ["python", "bot.py"]
