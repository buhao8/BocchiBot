import discord
from discord.ext import commands
import json
import settings
import asyncio
#testing PR
def load_configs():
    tmp = {}
    with open('config.json', 'r') as f:
        tmp = json.load(f)

    with open('tokens.json', 'r') as f:
        tokens = json.load(f)
        tmp["tokens"] = tokens

    settings.set(tmp)

def load_commands(bot):
    cogs = ['modules.Testing']

    from modules import __all__ as cogs
    print(cogs)

    for cog in cogs:
        asyncio.run(bot.load_extension(f'modules.{cog}'))

if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.message_content = True

    load_configs()

    bot = commands.Bot(
            command_prefix=settings.get()["prefix"],
            intents=intents,
            activity=discord.Activity(name="Kessoku Band", type=discord.ActivityType.listening))

    load_commands(bot)


    bot.run(settings.get()["tokens"]["discord"])
