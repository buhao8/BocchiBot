import discord
from discord.ext import commands
import json
import re
import validators
import random

class BotStuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('words.json', 'r') as f:
            self.words = json.load(f)

    @commands.Cog.listener()
    async def on_message(self, ctx):
        author_id = str(ctx.author.id)

        if author_id in self.words:
            author_arr = self.words[author_id]
            msg = ctx.content.lower()

            for word in author_arr:
                # Initial matches
                escaped = re.escape(word)
                result = re.findall(escaped, msg)

                # Subtract out emote matches
                emote_escaped = "<:[^<:]*" + escaped + "[^:>]*:\\d+>"
                emotes = re.findall(emote_escaped, msg)

                # Subtract URL nonsense, stupidity part 2
                parts = msg.strip().split(" ")
                in_url = []
                for s in parts:
                    if validators.url(s):
                        in_url += re.findall(escaped, s)

                num_matches = len(result) - len(emotes) - len(in_url)

                if num_matches > 0:
                    val = author_arr[word] + num_matches
                    author_arr[word] = val
                    member = ctx.guild.get_member(ctx.author.id)
                    if random.randrange(5) == 0:
                        await ctx.channel.send(f"{member.display_name}'s `{word}` counter: {val}")
                    with open('words.json', 'w', encoding='utf-8') as f:
                        json.dump(self.words, f, ensure_ascii=False, indent=4)



async def setup(client):
    await client.add_cog(BotStuff(client))
