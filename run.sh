#!/bin/bash

# If .env doesn't exist, create it and prompt for token
if [ ! -f .env ]; then
    cp example.env .env
    echo ".env file created from example.env."

    read -p "Enter your Discord bot token: " TOKEN
    sed -i "s|DISCORD_TOKEN=.*|DISCORD_TOKEN=$TOKEN|" .env

    echo ".env updated with your token."
fi

# Build the Docker image
docker build -t discord-music-bot .

# Stop & remove existing container if it exists
if [ "$(docker ps -aq -f name=music-bot)" ]; then
    docker stop music-bot
    docker rm music-bot
fi

# Run container with env file and auto-restart
docker run -d \
  --name music-bot \
  --restart unless-stopped \
  --env-file $(pwd)/.env \
  discord-music-bot

echo "Bot is running!"
