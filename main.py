import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.loop_queue = []
bot.is_looping = False

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

TOKEN = os.getenv("DISCORD_TOKEN")

@bot.event
async def on_ready():
    print(f"🎶 Bot is online as {bot.user}")

class MusicControls(discord.ui.View):
    def __init__(self, ctx, title, url):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.title = title
        self.url = url

    @discord.ui.button(label="⏸ Pause", style=discord.ButtonStyle.secondary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.edit_message(content="⏸ Paused", view=self)

    @discord.ui.button(label="▶️ Resume", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.edit_message(content=f"▶️ Resumed: **{self.title}**", view=self)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc:
            vc.stop()
            await interaction.response.edit_message(content="⏹ Stopped playback.", view=None)

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.primary)
    async def toggle_loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot.is_looping = not bot.is_looping
        status = "🔁 Loop ON" if bot.is_looping else "➡️ Loop OFF"
        await interaction.response.edit_message(content=f"{status} | Now playing: **{self.title}**", view=self)

    @discord.ui.button(label="⏭ Skip", style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.edit_message(content="⏭ Skipped.", view=None)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send(f"✅ Joined **{ctx.author.voice.channel}**")
    else:
        await ctx.send("❌ You are not in a voice channel.")

@bot.command()
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        return await ctx.send("❌ Join a voice channel first.")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info['url']
        title = info.get('title', 'Unknown Title')

    source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)

    def after_playing(e):
        if bot.is_looping:
            coro = ctx.invoke(play, search=search)
        elif bot.loop_queue:
            next_song = bot.loop_queue.pop(0)
            coro = ctx.invoke(play, search=next_song)
        else:
            return
        fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        try:
            fut.result()
        except Exception as ex:
            print(f"Error: {ex}")

    vc = ctx.voice_client
    if vc.is_playing():
        bot.loop_queue.append(search)
        return await ctx.send("🔂 Added to queue.")
    vc.play(source, after=after_playing)

    view = MusicControls(ctx, title, url)
    await ctx.send(f"🎶 Now Playing: **{title}**", view=view)

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel.")
    else:
        await ctx.send("❌ I'm not in a voice channel.")

@bot.command()
async def queue(ctx):
    if not bot.loop_queue:
        await ctx.send("📭 Queue is empty.")
    else:
        queue_list = "\n".join(f"{i+1}. {song}" for i, song in enumerate(bot.loop_queue))
        await ctx.send(f"🎵 Current Queue:\n{queue_list}")

bot.run(TOKEN)
