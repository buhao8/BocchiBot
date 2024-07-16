import discord
from discord.ext import commands
import json
import re
import validators
import random

class LinksAndGames(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def wsj(self, ctx):
        await ctx.send("<https://www.wsj.com>")

    @commands.command()
    async def douga(self, ctx):
        await ctx.send("<https://douga.buhao.jp>")

    @commands.command()
    async def dropbox(self, ctx):
        await ctx.send("<https://buhao.jp/dropbox>")

    @commands.command()
    async def flip(self, ctx):
        if random.randrange(2) == 0:
            await ctx.send("heads")
        else:
            await ctx.send("tails")



async def setup(client):
    await client.add_cog(LinksAndGames(client))
