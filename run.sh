#!/bin/bash

# Check if .env exists
if [ ! -f .env ]; then
    cp example.env .env
    echo ".env file created from example.env. Please edit it with your bot token and settings."
    echo "Continuing with placeholder values..."
fi

# Build the Docker image
docker build -t discord-music-bot .

# Run the container with env file and auto-restart
docker run -d --name music-bot --env-file .env --restart unless-stopped discord-music-bot

echo "Bot is running!"
