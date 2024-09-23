import discord
from discord.ext import commands
import json
import settings
import asyncio

def load_configs():
    tmp = {}
    with open('config.json', 'r') as f:
        tmp = json.load(f)

    with open('tokens.json', 'r') as f:
        tokens = json.load(f)
        tmp["tokens"] = tokens

    settings.set(tmp)

def load_commands(bot):
    from modules import __all__ as cogs
    print(cogs)

    for cog in cogs:
        if cog in settings.get()["disabled_cogs"]:
            print(f"Skipping cog {cog}")
        else:
            asyncio.run(bot.load_extension(f'modules.{cog}'))

if __name__ == '__main__':
    intents = discord.Intents.all()

    load_configs()

    activity_map = {
        "LISTENING": discord.ActivityType.listening,
        "WATCHING": discord.ActivityType.watching,
        "PLAYING": discord.ActivityType.playing,
    }

    cfg_activity = settings.get()["activity"]

    activity = None

    if len(cfg_activity) == 2:
        activity = discord.Activity(name=cfg_activity[1], type=activity_map[cfg_activity[0]])

    bot = commands.Bot(
            command_prefix=settings.get()["prefix"],
            intents=intents,
            activity=activity)

    load_commands(bot)


    bot.run(settings.get()["tokens"]["discord"])
