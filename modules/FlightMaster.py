import discord
from discord.ext import commands
import requests
import settings

class FlightMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def email(self, ctx):
        msg = ctx.message
        parts = msg.content.split()
        receiver = parts[1]
        message = parts[2:]

        requests.post('https://api.mailgun.net/v3/buhao.jp/messages',
                      auth=('api', settings.get()["tokens"]["mailgun"]),
                      data={'from': 'FlightMaster <flightmaster@buhao.jp>',
                            'to': [receiver],
                            'subject': 'JAL F Flight Found!',
                            'text': '',
                            'html': 'Flight found for JFK->HND on Jan 32, 2011<br/>Link: https://douga.buhao.jp/',
                           })
        await ctx.reply(f"Sent email to {receiver}")

async def setup(client):
    await client.add_cog(FlightMaster(client))
