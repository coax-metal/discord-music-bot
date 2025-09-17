#!/bin/bash
set -e

# Ensure we are in the script's directory
cd "$(dirname "$0")"

# Step 1: Copy example.env to .env if it doesn't exist
if [ ! -f .env ]; then
    cp example.env .env
    echo ".env file created from example.env."
fi

# Step 2: Prompt for Discord token
read -p "Enter your Discord bot token: " TOKEN

# Validate input
if [ -z "$TOKEN" ]; then
    echo "Error: Token cannot be empty."
    exit 1
fi

# Step 3: Update .env with the token (overwrite if it exists)
if grep -q "^DISCORD_TOKEN=" .env; then
    sed -i "s|^DISCORD_TOKEN=.*|DISCORD_TOKEN=$TOKEN|" .env
else
    echo "DISCORD_TOKEN=$TOKEN" >> .env
fi

echo ".env updated with your token."

# Step 4: Build Docker image
docker build -t discord-music-bot .

# Step 5: Stop & remove existing container if it exists
if [ "$(docker ps -aq -f name=music-bot)" ]; then
    docker stop music-bot
    docker rm music-bot
fi

# Step 6: Run container with auto-restart and .env
docker run -d \
  --name music-bot \
  --restart unless-stopped \
  --env-file "$(pwd)/.env" \
  discord-music-bot

echo "Bot is running!"
