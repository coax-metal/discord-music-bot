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

FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    "-nostdin"
)

FFMPEG_OPTIONS = (
    '-vn -bufsize 512k '
    '-af "aresample=resampler=soxr:osr=48000:dither_method=triangular"'
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

    async def add(
        self,
        track: Track,
        channel: discord.abc.Messageable,
    ) -> int:
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
                    await asyncio.wait_for(
                        self.next_track.wait(),
                        timeout=300,
                    )
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
                        f"Skipping **{track.title}** because yt-dlp "
                        f"could not refresh it: `{exc}`"
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

            voice.play(
                source,
                after=after_playback,
            )

            if self.text_channel and track.announce_on_play:
                await self.text_channel.send(
                    f"Now playing: **{track.title}** "
                    f"`{track.duration_text}`"
                )

            await done.wait()

            self.current = None


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self.players: dict[int, GuildPlayer] = {}

    def player_for(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer(
                self,
                guild_id,
            )

        return self.players[guild_id]

    async def setup_hook(self) -> None:
        if GUILD_ID:
            guild = discord.Object(
                id=int(GUILD_ID)
            )

            self.tree.copy_global_to(guild=guild)

            await self.tree.sync(
                guild=guild
            )

            logger.info(
                "Synced commands to guild %s",
                GUILD_ID,
            )

        else:
            await self.tree.sync()

            logger.info(
                "Synced global commands"
            )


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

    if URL_PATTERN.match(query):
        return query

    return f"ytsearch1:{query}"


def extract_track_sync(
    query: str,
    requested_by: str,
) -> Track:

    with yt_dlp.YoutubeDL(
        ytdlp_options()
    ) as ydl:

        info = ydl.extract_info(
            normalize_query(query),
            download=False,
        )

    if "entries" in info:
        entries = [
            entry
            for entry in info["entries"]
            if entry
        ]

        if not entries:
            raise ValueError(
                "No playable results found."
            )

        info = entries[0]

    stream_url = info.get("url")
    title = info.get("title") or "Unknown title"

    webpage_url = (
        info.get("webpage_url")
        or info.get("original_url")
        or query
    )

    duration = info.get("duration")

    if not stream_url:
        raise ValueError(
            "yt-dlp did not return a stream URL."
        )

    return Track(
        title=title,
        webpage_url=webpage_url,
        stream_url=stream_url,
        requested_by=requested_by,
        duration=duration,
    )


async def extract_track(
    query: str,
    requested_by: str,
) -> Track:

    return await asyncio.to_thread(
        extract_track_sync,
        query,
        requested_by,
    )


def refresh_track_stream_sync(
    track: Track,
) -> Track:

    with yt_dlp.YoutubeDL(
        ytdlp_options()
    ) as ydl:

        info = ydl.extract_info(
            track.webpage_url,
            download=False,
        )

    if "entries" in info:
        entries = [
            entry
            for entry in info["entries"]
            if entry
        ]

        if not entries:
            raise ValueError(
                "No playable results found."
            )

        info = entries[0]

    stream_url = info.get("url")

    if not stream_url:
        raise ValueError(
            "yt-dlp did not return a stream URL."
        )

    return Track(
        title=info.get("title") or track.title,
        webpage_url=(
            info.get("webpage_url")
            or track.webpage_url
        ),
        stream_url=stream_url,
        requested_by=track.requested_by,
        duration=(
            info.get("duration")
            or track.duration
        ),
        announce_on_play=track.announce_on_play,
    )


async def refresh_track_stream(
    track: Track,
) -> Track:

    return await asyncio.to_thread(
        refresh_track_stream_sync,
        track,
    )


def require_guild_id(
    interaction: discord.Interaction,
) -> int:

    if not interaction.guild_id:
        raise app_commands.AppCommandError(
            "This command only works in a server."
        )

    return interaction.guild_id


async def ensure_voice(
    interaction: discord.Interaction,
) -> discord.VoiceClient:

    if not interaction.guild:
        raise app_commands.AppCommandError(
            "This command only works in a server."
        )

    user = interaction.user

    if (
        not isinstance(user, discord.Member)
        or not user.voice
        or not user.voice.channel
    ):
        raise app_commands.AppCommandError(
            "You must be in a voice channel."
        )

    existing = interaction.guild.voice_client

    if existing:
        if (
            existing.channel
            and existing.channel != user.voice.channel
        ):
            await existing.move_to(
                user.voice.channel
            )

        return existing

    return await user.voice.channel.connect()


@bot.tree.command(
    name="play",
    description="Play a YouTube song or search result",
)
@app_commands.describe(
    query="YouTube URL or search terms",
)
async def play(
    interaction: discord.Interaction,
    query: str,
):
    await interaction.response.defer()

    try:
        await ensure_voice(interaction)

        guild_id = require_guild_id(interaction)

        track = await extract_track(
            query,
            interaction.user.display_name,
        )

        player = bot.player_for(guild_id)

        position = await player.add(
            track,
            interaction.channel,
        )

        if (
            player.current is None
            and position == 1
        ):
            message = (
                f"Added **{track.title}** "
                "and starting playback."
            )

        else:
            message = (
                f"Queued **{track.title}** "
                f"at position **{position}**."
            )

        await interaction.followup.send(
            message
        )

    except Exception as exc:
        logger.exception(
            "Play command failed"
        )

        await interaction.followup.send(
            f"Could not play that track: `{exc}`",
            ephemeral=True,
        )


@bot.tree.command(
    name="skip",
    description="Skip the current song",
)
async def skip(
    interaction: discord.Interaction,
):
    try:
        guild_id = require_guild_id(interaction)

        player = bot.player_for(guild_id)

        if await player.skip():
            await interaction.response.send_message(
                "Skipped."
            )
        else:
            await interaction.response.send_message(
                "Nothing is currently playing.",
                ephemeral=True,
            )

    except Exception as exc:
        logger.exception(
            "Skip command failed"
        )

        await interaction.response.send_message(
            f"Could not skip: `{exc}`",
            ephemeral=True,
        )


@bot.tree.command(
    name="stop",
    description="Stop playback, clear the queue, and disconnect",
)
async def stop(
    interaction: discord.Interaction,
):
    try:
        guild_id = require_guild_id(interaction)

        player = bot.player_for(guild_id)

        await player.stop()

        await interaction.response.send_message(
            "Playback stopped and queue cleared."
        )

    except Exception as exc:
        logger.exception(
            "Stop command failed"
        )

        await interaction.response.send_message(
            f"Could not stop playback: `{exc}`",
            ephemeral=True,
        )


@bot.tree.command(
    name="queue",
    description="Show the music queue",
)
async def queue(
    interaction: discord.Interaction,
):
    try:
        guild_id = require_guild_id(interaction)

        player = bot.player_for(guild_id)

        lines = []

        if player.current:
            lines.append(
                "Now playing:\n"
                f"**{player.current.title}** "
                f"`{player.current.duration_text}`"
            )

        if player.queue:
            lines.append("\nUp next:")

            for index, track in enumerate(
                list(player.queue)[:10],
                start=1,
            ):
                lines.append(
                    f"{index}. **{track.title}** "
                    f"`{track.duration_text}`"
                )

            if len(player.queue) > 10:
                lines.append(
                    f"...and {len(player.queue) - 10} more."
                )

        if not lines:
            await interaction.response.send_message(
                "The queue is empty."
            )
            return

        await interaction.response.send_message(
            "\n".join(lines)
        )

    except Exception as exc:
        logger.exception(
            "Queue command failed"
        )

        await interaction.response.send_message(
            f"Could not display queue: `{exc}`",
            ephemeral=True,
        )


@bot.tree.command(
    name="nowplaying",
    description="Show the currently playing song",
)
async def nowplaying(
    interaction: discord.Interaction,
):
    guild_id = require_guild_id(interaction)

    player = bot.player_for(guild_id)

    if not player.current:
        await interaction.response.send_message(
            "Nothing is currently playing.",
            ephemeral=True,
        )
        return

    track = player.current

    await interaction.response.send_message(
        f"Now playing: **{track.title}**\n"
        f"Duration: `{track.duration_text}`\n"
        f"Requested by: **{track.requested_by}**\n"
        f"{track.webpage_url}"
    )


@bot.tree.command(
    name="pause",
    description="Pause playback",
)
async def pause(
    interaction: discord.Interaction,
):
    if not interaction.guild:
        await interaction.response.send_message(
            "This command only works in a server.",
            ephemeral=True,
        )
        return

    voice = interaction.guild.voice_client

    if not voice or not voice.is_playing():
        await interaction.response.send_message(
            "Nothing is currently playing.",
            ephemeral=True,
        )
        return

    voice.pause()

    await interaction.response.send_message(
        "Paused."
    )


@bot.tree.command(
    name="resume",
    description="Resume playback",
)
async def resume(
    interaction: discord.Interaction,
):
    if not interaction.guild:
        await interaction.response.send_message(
            "This command only works in a server.",
            ephemeral=True,
        )
        return

    voice = interaction.guild.voice_client

    if not voice or not voice.is_paused():
        await interaction.response.send_message(
            "Playback is not paused.",
            ephemeral=True,
        )
        return

    voice.resume()

    await interaction.response.send_message(
        "Resumed."
    )


@bot.tree.command(
    name="join",
    description="Join your voice channel",
)
async def join(
    interaction: discord.Interaction,
):
    try:
        voice = await ensure_voice(interaction)

        await interaction.response.send_message(
            f"Joined **{voice.channel.name}**."
        )

    except Exception as exc:
        await interaction.response.send_message(
            f"Could not join: `{exc}`",
            ephemeral=True,
        )


@bot.tree.command(
    name="leave",
    description="Leave the voice channel",
)
async def leave(
    interaction: discord.Interaction,
):
    if not interaction.guild:
        await interaction.response.send_message(
            "This command only works in a server.",
            ephemeral=True,
        )
        return

    voice = interaction.guild.voice_client

    if not voice:
        await interaction.response.send_message(
            "I'm not connected to a voice channel.",
            ephemeral=True,
        )
        return

    guild_id = interaction.guild.id

    if guild_id in bot.players:
        bot.players[guild_id].queue.clear()
        bot.players[guild_id].current = None

    await voice.disconnect(force=True)

    await interaction.response.send_message(
        "Disconnected."
    )


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    logger.exception(
        "Application command error",
        exc_info=error,
    )

    message = str(error)

    if interaction.response.is_done():
        await interaction.followup.send(
            f"Error: `{message}`",
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            f"Error: `{message}`",
            ephemeral=True,
        )


@bot.event
async def on_ready():
    logger.info(
        "Logged in as %s (%s)",
        bot.user,
        bot.user.id if bot.user else "unknown",
    )


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN environment variable is not set."
        )

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
