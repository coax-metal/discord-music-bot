import discord
from discord.ext import commands
import asyncio
import yt_dlp
import os

# --- Load token from environment ---
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("No BOT_TOKEN environment variable found!")

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True  # Needed for commands
bot = commands.Bot(command_prefix="!", intents=intents)

# --- yt-dlp / FFmpeg Options ---
ytdl_format_options = {
    'format': 'bestaudio/best',
    'quiet': True,
    'noplaylist': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

# --- Song Queue ---
queues = {}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# --- Queue Helper ---
async def play_next(ctx):
    if queues.get(ctx.guild.id):
        next_song = queues[ctx.guild.id].pop(0)
        ctx.voice_client.play(next_song, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f'Now playing: {next_song.title}')
    else:
        await ctx.voice_client.disconnect()

# --- Bot Commands ---
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"Joined {channel}")
    else:
        await ctx.send("You're not in a voice channel!")

@bot.command()
async def play(ctx, *, url):
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You're not in a voice channel!")
            return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        if ctx.guild.id not in queues:
            queues[ctx.guild.id] = []

        if not ctx.voice_client.is_playing():
            ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
            await ctx.send(f'Now playing: {player.title}')
        else:
            queues[ctx.guild.id].append(player)
            await ctx.send(f'Added to queue: {player.title}')

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipped current song.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queues[ctx.guild.id] = []
        await ctx.send("Stopped playback and cleared queue.")

@bot.command()
async def queue(ctx):
    if queues.get(ctx.guild.id) and len(queues[ctx.guild.id]) > 0:
        queue_list = '\n'.join([f"{i+1}. {song.title}" for i, song in enumerate(queues[ctx.guild.id])])
        await ctx.send(f"Current queue:\n{queue_list}")
    else:
        await ctx.send("Queue is empty.")

# --- Run the bot ---
bot.run(TOKEN)
