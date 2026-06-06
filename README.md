# Discord Music Bot

A lightweight Discord music bot that plays YouTube audio with high-quality streaming.

## Features

- Stream YouTube videos or search results directly to Discord voice channels
- Minimal latency and smooth playback with optimized buffering
- Supports live streams and playlists
- Simple slash commands for easy control

## Commands

- `/play <url or search>`: Play a YouTube URL or search for a song
- `/queue`: Show what's currently playing and upcoming tracks
- `/skip`: Skip the current track
- `/pause`: Pause playback
- `/resume`: Resume playback
- `/stop`: Stop playback and disconnect from the voice channel

## Setup

### 1. Discord Bot Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Go to the **Bot** tab and click **Add Bot**
4. Under **TOKEN**, click **Copy** to copy your bot token (keep this secret!)
5. Go to **OAuth2** → **URL Generator**
6. Select scopes: `bot` and `applications.commands`
7. Select permissions: `Connect`, `Speak`, `Use Voice Activity`, `Send Messages`, `Use Slash Commands`
8. Copy the generated URL and open it in your browser to invite the bot to your server

### 2. Installation on Unraid

1. Open a terminal on your Unraid server
2. Clone the repository:
   ```bash
   cd /mnt/user/appdata
   git clone https://github.com/coax-metal/discord-music-bot.git
   cd discord-music-bot
   ```

3. Create a `.env` file with your settings:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and set:
   ```
   DISCORD_TOKEN=your-bot-token-here
   GUILD_ID=your-server-id-here
   ```
   - Find your server ID: Enable Developer Mode in Discord settings, right-click your server, and copy the ID
   - `GUILD_ID` is optional but commands appear faster with it

5. In Unraid Docker UI:
   - Click **Add Container**
   - Set **Name** to `discord-music-bot`
   - Set **Repository** to `discord-music-bot:latest`
   - Set **Network Type** to `bridge`
   - Click **Add another Path, Port, Variable, Label or Device** and add your environment file:
     - **Config Type**: `Variable`
     - **Name**: `DISCORD_TOKEN`
     - **Value**: Your bot token
   - Click **Apply**

6. The container will build and start automatically

### 3. Local Testing (Docker)

```bash
cp .env.example .env
# Edit .env with your bot token
docker build -t discord-music-bot:latest .
docker run --rm --env-file .env discord-music-bot:latest
```

## Updating

To update to the latest version:

```bash
cd /mnt/user/appdata/discord-music-bot
git pull
docker-compose down
docker-compose up -d --build
```

Or in Unraid Docker UI, find the container and click **Force Update**.
   - `GUILD_ID`: your Discord server ID, optional but recommended
   - `UPDATE_YTDLP_ON_START`: `true`
   - `YTDLP_COOKIES_FILE`: optional, usually blank
   - `LOG_LEVEL`: `INFO`
7. Optional cookies path:
   - Container path: `/cookies`
   - Host path: `/mnt/user/appdata/discord-music-bot/cookies`
   - Access mode: read-only
8. Apply.

To run it without the Unraid UI:

```bash
docker run -d \
  --name discord-music-bot \
  --restart unless-stopped \
  --env-file /mnt/user/appdata/discord-music-bot/.env \
  -v /mnt/user/appdata/discord-music-bot/cookies:/cookies:ro \
  discord-music-bot:latest
```

To update later from GitHub:

```bash
cd /mnt/user/appdata/discord-music-bot
git pull
docker build -t discord-music-bot:latest .
docker restart discord-music-bot
```

## Keeping yt-dlp Current

`docker-entrypoint.sh` runs this at every startup:

```bash
python -m pip install --no-cache-dir --upgrade yt-dlp
```

Leave this in `.env`:

```text
UPDATE_YTDLP_ON_START=true
```

To force a fresh update later, restart the container. If YouTube changes something while the bot is already running, a restart is enough.

## Optional Cookies

If YouTube asks for sign-in or blocks some videos, export a `cookies.txt` file and mount it:

```text
./cookies/youtube.cookies.txt
```

Then set:

```text
YTDLP_COOKIES_FILE=/cookies/youtube.cookies.txt
```

Do not commit or share cookies. They are account credentials.
