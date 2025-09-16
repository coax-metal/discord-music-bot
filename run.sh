#!/bin/bash

# Copy example.env if .env does not exist
if [ ! -f .env ]; then
    cp example.env .env
    echo ".env file created. Please edit it with your bot token and settings."
    exit 0
fi

# Build the Docker image
docker build -t discord-music-bot .

# Run the container with env file
docker run -d --name music-bot --env-file .env --restart unless-stopped discord-music-bot

echo "Bot is running!"
