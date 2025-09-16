#!/bin/bash

# Build the Docker image
docker build -t discord-music-bot .

# Run the container with env file
docker run -d --name music-bot --env-file .env discord-music-bot

echo "Bot is running!"
