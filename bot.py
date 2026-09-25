import asyncio
import logging
import os
import re
from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional

import discord
import yt_dlp
from discord import app_commands
from discord.ext import commands


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
YTDLP_COOKIES_FILE = os.getenv("YTDLP_COOKIES_FILE")

# High-fidelity audio configurations using the SoX high-end resampler engine
FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-nostdin"
)
FFMPEG_OPTIONS = (
    '-vn -bufsize 512k -af "aresample=resampler=soxr:osr=48000:dither_method=triangular"'
)

URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("music-bot")


@dataclass
class Track:
    title: str
    webpage_url: str
    stream_url: str
    requested_by: str
    duration: Optional[int] = None
    announce_on_play: bool = True

    @property
    def duration_text(self) -> str:
        if not self.duration:
            return "live/unknown"
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class GuildPlayer:
    def __init__(self, bot: commands.Bot, guild_id: int):
        self.bot = bot
        self.guild_id = guild_id
        self.queue: Deque[Track] = deque()
        self.current: Optional[Track] = None
        self.text_channel: Optional[discord.abc.Messageable] = None
        self.next_track = asyncio.Event()
        self.player_task = bot.loop.create_task(self.player_loop())

    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        guild = self.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    async def add(self, track: Track, channel: discord.abc.Messageable) -> int:
        self.text_channel = channel
        self.queue.append(track)
        position = len(self.queue)
        self.next_track.set()
        return position

    async def skip(self) -> bool:
        voice = self.voice_client
        if voice and voice.is_playing():
            voice.stop()
            return True
        return False

    async def stop(self) -> None:
        self.queue.clear()
        self.current = None
        voice = self.voice_client
        if voice:
            voice.stop()
            await voice.disconnect(force=True)

    async def player_loop(self) -> None:
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.next_track.clear()

            if not self.queue:
                try:
                    await asyncio.wait_for(self.next_track.wait(), timeout=300)
                    continue
                except asyncio.TimeoutError:
                    voice = self.voice_client
                    if voice and not voice.is_playing():
                        await voice.disconnect(force=True)
                    continue

            track = self.queue.popleft()
            voice = self.voice_client
            if not voice:
                self.current = None
                continue

            try:
                track = await refresh_track_stream(track)
            except Exception as exc:
                logger.exception("Could not refresh stream URL")
                if self.text_channel:
                    await self.text_channel.send(
                        f"Skipping **{track.title}** because yt-dlp could not refresh it: `{exc}`"
                    )
                self.current = None
                continue

            self.current = track
            done = asyncio.Event()

            def after_playback(error: Optional[Exception]) -> None:
                if error:
                    logger.warning("Playback error: %s", error)
                self.bot.loop.call_soon_threadsafe(done.set)

            source = discord.FFmpegOpusAudio(
                track.stream_url,
                before_options=FFMPEG_BEFORE_OPTIONS,
                options=FFMPEG_OPTIONS,
            )
            voice.play(source, after=after_playback)

            if self.text_channel and track.announce_on_play:
                await self.text_channel.send(
                    f"Now playing: **{track.title}** `{track.duration_text}`"
                )

            await done.wait()
            self.current = None


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.players: dict[int, GuildPlayer] = {}

    def player_for(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer(self, guild_id)
        return self.players[guild_id]

    async def setup_hook(self) -> None:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Synced commands to guild %s", GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("Synced global commands")


bot = MusicBot()


def ytdlp_options() -> dict:
    options = {
        "format": "bestaudio[acodec=opus]/bestaudio/best",
        "quiet": True,
        "default_search": "ytsearch1",
        "noplaylist": True,
        "extract_flat": False,
        "source_address": "0.0.0.0",
    }
    if YTDLP_COOKIES_FILE:
        options["cookiefile"] = YTDLP_COOKIES_FILE
    return options


def normalize_query(query: str) -> str:
    query = query.strip()
    return query if URL_PATTERN.match(query) else f"ytsearch1:{query}"


def extract_track_sync(query: str, requested_by: str) -> Track:
    with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
        info = ydl.extract_info(normalize_query(query), download=False)

    if "entries" in info:
        entries = [entry for entry in info["entries"] if entry]
        if not entries:
            raise ValueError("No playable results found.")
        info = entries[0]

    stream_url = info.get("url")
    title = info.get("title") or "Unknown title"
    webpage_url = info.get("webpage_url") or info.get("original_url") or query
    duration = info.get("duration")

    if not stream_url:
        raise ValueError("yt-dlp did not return a stream URL.")

    return Track(
        title=title,
        webpage_url=webpage_url,
        stream_url=stream_url,
        requested_by=requested_by,
        duration=duration,
    )


async def extract_track(query: str, requested_by: str) -> Track:
    return await asyncio.to_thread(extract_track_sync, query, requested_by)


def refresh_track_stream_sync(track: Track) -> Track:
    with yt_dlp.YoutubeDL(ytdlp_options()) as ydl:
        info = ydl.extract_info(track.webpage_url, download=False)

    if "entries" in info:
        entries = [entry for entry in info["entries"] if entry]
        if not entries:
            raise ValueError("No playable results found.")
        info = entries[0]

    stream_url = info.get("url")
    if not stream_url:
        raise ValueError("yt-dlp did not return a stream URL.")

    return Track(
        title=info.get("title") or track.title,
        webpage_url=info.get("webpage_url") or track.webpage_url,
        stream_url=stream_url,
        requested_by=track.requested_by,
        duration=info.get("duration") or track.duration,
        announce_on_play=track.announce_on_play,
    )


async def refresh_track_stream(track: Track) -> Track:
    return await asyncio.to_thread(refresh_track_stream_sync, track)


def require_guild_id(interaction: discord.Interaction) -> int:
    if not interaction.guild_id:
        raise app_commands.AppCommandError("This command only works in a server.")
    return interaction.guild_id


async def ensure_voice(interaction: discord.Interaction) -> discord.VoiceClient:
    if not interaction.guild:
        raise app_commands.AppCommandError("This command only works in a server.")

    user = interaction.user
    if not user.voice or not user.voice.channel:
        raise app_commands.AppCommandError("You must be in a voice channel.")

    if interaction.guild.voice_client:
        return interaction.guild.voice_client

    return await user.voice.channel.connect()



if __name__ == "__main__":
    main()
