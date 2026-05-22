# Discord Music Bot

A lightweight Discord music bot that streams audio with `yt-dlp` and `ffmpeg`.

It updates `yt-dlp` every time the container starts, so normal restarts pick up the newest extractor fixes without rebuilding the image.

## Commands

- `/play <url or search>`: queue a YouTube URL or search result
- `/queue`: show the current track and upcoming tracks
- `/skip`: skip the current track
- `/pause`: pause playback
- `/resume`: resume playback
- `/stop`: clear the queue and disconnect

## Discord Setup

1. Create an application at the Discord Developer Portal.
2. Add a bot user and copy the bot token.
3. Enable these OAuth2 scopes when inviting it:
   - `bot`
   - `applications.commands`
4. Enable these bot permissions:
   - `Connect`
   - `Speak`
   - `Use Voice Activity`
   - `Send Messages`
   - `Use Slash Commands`

For easiest first setup, put your Discord server ID in `GUILD_ID`. Slash commands usually appear immediately for that server. Without `GUILD_ID`, commands are global and Discord can take a while to show them.

## Local Run

```bash
cp .env.example .env
# edit .env and set DISCORD_TOKEN
docker build -t discord-music-bot:latest .
docker run --rm --env-file .env discord-music-bot:latest
```

## Publish To GitHub

From this folder on your development machine:

```bash
git init
git add .
git commit -m "Initial Discord music bot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/discord-music-bot.git
git push -u origin main
```

Create the empty GitHub repo first at:

```text
https://github.com/new
```

Use `discord-music-bot` as the repo name. Do not commit `.env` or anything in `cookies/`; both are ignored.

## Unraid Install

Install from GitHub on your Unraid server:

```bash
cd /mnt/user/appdata
git clone https://github.com/YOUR_USERNAME/discord-music-bot.git
cd discord-music-bot
cp .env.example .env
```

Edit `.env` and set at least:

```text
DISCORD_TOKEN=your-real-token
GUILD_ID=your-discord-server-id
UPDATE_YTDLP_ON_START=true
```

Then build the image:

```bash
docker build -t discord-music-bot:latest .
```

Now add it in the normal Unraid Docker UI:

1. Go to **Docker**.
2. Click **Add Container**.
3. Set **Name** to `discord-music-bot`.
4. Set **Repository** to `discord-music-bot:latest`.
5. Set **Network Type** to `bridge`.
6. Add these environment variables:
   - `DISCORD_TOKEN`: your Discord bot token
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
