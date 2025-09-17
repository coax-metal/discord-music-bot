#!/bin/bash
set -e
cd "$(dirname "$0")"

# Step 1: Copy example.env if missing
if [ ! -f .env ]; then
    cp example.env .env
    echo ".env file created from example.env."
fi

# Step 2: Prompt for token
read -p "Enter your Discord bot token: " TOKEN
if [ -z "$TOKEN" ]; then
    echo "Error: Token cannot be empty."
    exit 1
fi

# Step 3: Ensure token is on its own line
# Remove any existing DISCORD_TOKEN line
sed -i '/^DISCORD_TOKEN=/d' .env

# Append new token
echo "DISCORD_TOKEN=$TOKEN" >> .env

echo ".env updated safely with your token."

# Step 4: Build Docker image
docker build -t discord-music-bot .

# Step 5: Stop & remove existing container
if [ "$(docker ps -aq -f name=music-bot)" ]; then
    docker stop music-bot
    docker rm music-bot
fi

# Step 6: Run container
docker run -d \
  --name music-bot \
  --restart unless-stopped \
  --env-file "$(pwd)/.env" \
  discord-music-bot

echo "Bot is running!"
