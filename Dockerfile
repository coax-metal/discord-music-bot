# Use official Python slim image
FROM python:3.12-slim

# Install FFmpeg and dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg git curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy bot files
COPY bot.py requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose nothing (Discord bot uses outgoing connections)
# Set default command
CMD ["python", "bot.py"]
