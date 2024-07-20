import discord
from discord.ext import commands
import json
import re
import validators
import random
import sqlite3
from datetime import datetime

class BotStuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('words.json', 'r') as f:
            self.words = json.load(f)

        self.con = sqlite3.connect("messages.db")
        self.cur = self.con.cursor()


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

        await insert_message(ctx, self.cur, self.con)


    @commands.Cog.listener()
    async def on_message_delete(self, ctx):

        res = self.cur.execute(f"select * from messages where id={ctx.id}")
        results = res.fetchall()

        if len(results) > 1:
            await ctx.send(f"More than one message with id {ctx.id}")
            return
        elif len(results) < 1:
            await ctx.send(f"Message does not exist with id {ctx.id}.  Inserting...")
            await insert_message(ctx, cur, con)

        del_time = datetime.now().timestamp()
        self.cur.execute(f"update messages set deleted_time='{del_time}' where id={ctx.id}")
        self.con.commit()


    @commands.command()
    async def deleted(self, ctx, username):
        res = self.cur.execute((
        #await ctx.reply((
            f"select u.name, m.content "
            f"from messages as m "
            f"join users as u "
                f"on m.author_id=u.id "
                    f"where m.deleted_time!='0' and u.name='{username}' "
                        f"order by m.deleted_time desc limit 5"))

        result = res.fetchall()

        ret = f"{username}'s last {len(result)} deleted messages:\n\n"
        for msg in result:
            ret += f"- {msg[1]}\n\n"

        await ctx.send(ret)


async def insert_message(ctx, cur, con):
    # Text
    cur.execute("insert into messages values "
                + f"({ctx.id},"
                + f"{ctx.author.id},"
                + f"{ctx.guild.id},"
                + f"{ctx.channel.id},"
                + f"'{ctx.created_at.timestamp()}',"
                + f"'0',"
                + f"'" + ctx.content.replace("'", "''") + "')")
    con.commit()

    for a in ctx.attachments:
        got = False
        data = None
        for cached in [False, True]:
            try:
                data = await a.read(use_cached=cached)
                got = True
                break
            except discord.HTTPException:
                console.log("HTTPException while saving blob")
            except discord.Forbidden:
                console.log("Forbidden while saving blob")
            except discord.NotFound:
                console.log("NotFound whiel saving blob, was it deleted?")

        if not got:
            return

        cur.execute("insert into blobs values (?, ?, ?, ?)",
                    (a.id, ctx.id, a.filename, sqlite3.Binary(data)))
        con.commit()


async def setup(client):
    await client.add_cog(BotStuff(client))
