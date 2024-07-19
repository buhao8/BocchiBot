import discord
from discord import FFmpegPCMAudio
from discord.ext import commands
import json
import re
import validators
import random
from  yt_dlp import YoutubeDL

class MusicBox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx):
        channel = ctx.author.voice.channel
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_connected():
            await voice.move_to(channel)
        else:
            voice = await channel.connect()

    @commands.command()
    async def play(self, ctx, url):
        YDL_OPTIONS = {'format': 'bestaudio', 'noplaylist': 'True'}
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if not voice.is_playing():
            with YoutubeDL(YDL_OPTIONS) as ydl:
                info = ydl.extract_info(url, download=False)
            URL = info['url']
            voice.play(FFmpegPCMAudio(URL, **FFMPEG_OPTIONS))
            voice.source = discord.PCMVolumeTransformer(voice.source, volume=1.0)
            voice.source.volume = 0.2
            await ctx.send('Bot is playing')
        else:
            await ctx.send("Bot is already playing")
            return

    @commands.command()
    async def vol(self, ctx, volume: float):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_playing():
            voice.source.volume = 0.5 * min(volume, 1.0)

    @commands.command()
    async def resume(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and not voice.is_playing():
            voice.resume()
            await ctx.send('Resuming')
        elif voice:
            await ctx.send('Nothing to resume?')

    @commands.command()
    async def pause(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_playing():
            voice.pause()
            await ctx.send('Paused')
        else:
            await ctx.send('Nothing to pause?')

    @commands.command()
    async def stop(self, ctx):
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if voice and voice.is_playing():
            voice.stop()
            await ctx.send('Stopping...')


async def setup(client):
    await client.add_cog(MusicBox(client))
