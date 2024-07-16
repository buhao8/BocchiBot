import discord
from discord.ext import commands

class Testing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def ping(self, ctx):
        await ctx.reply('pong')

async def setup(client):
    await client.add_cog(Testing(client))
