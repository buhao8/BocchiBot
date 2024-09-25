import discord
from discord.ext import commands
import json
import re
import validators
import random
import sqlite3
from datetime import datetime
import modules.FlightMaster
import settings

class BotStuff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        with open('words.json', 'r') as f:
            self.words = json.load(f)

        self.con = sqlite3.connect("messages.db")
        self.cur = self.con.cursor()


    @commands.Cog.listener()
    async def on_ready(self):
        print("READY botstuff")


    @commands.Cog.listener()
    async def on_message(self, ctx):
        author_id = str(ctx.author.id)

        await insert_message(ctx, self.cur, self.con)

        if "storage" in ctx.channel.category.name.lower():
            return

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
                parts = msg.strip().split()
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


    @commands.Cog.listener()
    async def on_message_delete(self, ctx):

        if ctx.author.id == self.bot.user.id:
            async for entry in ctx.guild.audit_logs(limit=1):
                deleter = entry.user
            await ctx.channel.send(f"{deleter.mention} fuck you")

        res = self.cur.execute(f"select * from messages where id={ctx.id}")
        results = res.fetchall()

        if len(results) < 1:
            #await ctx.channel.send(f"Message does not exist with id {ctx.id}.  Inserting...")
            await insert_message(ctx, self.cur, self.con)

        del_time = datetime.now().timestamp()
        self.cur.execute(f"update messages set deleted_time='{del_time}' where id={ctx.id}")
        self.con.commit()


    @commands.Cog.listener()
    async def on_message_edit(self, ctx, after):
        if ctx.id != after.id:
            await ctx.channel.send(f"id mismatch: {ctx.id} != {after.id}")
            return

        res = self.cur.execute(f"select * from messages where id={ctx.id}")
        results = res.fetchall()

        await insert_message(after, self.cur, self.con)


    @commands.command()
    async def deleted(self, ctx, username):
        res = self.cur.execute((
            f"select u.name, m.content "
            f"from messages as m "
            f"join users as u "
                f"on m.author_id=u.id "
                    f"where m.deleted_time!='0' and u.name='{username}' "
                        f"order by m.deleted_time desc limit 5"))

        result = res.fetchall()

        title = f"{username}'s last {len(result)} deleted messages:\n\n"
        ret = ""
        for msg in result:
            ret += f"- {msg[1]}\n\n"

        await ctx.channel.send(embed = discord.Embed(title=title, description=ret))

    @commands.command(hidden=True)
    async def fbackup(self, ctx):
        if not is_owner(ctx.author.id):
            await ctx.reply("You are not in the sudoers file.  This incident will be reported.")
            return

        guild = ctx.guild
        await ctx.channel.send(str(guild))

        for channel in guild.text_channels:
            perms = channel.permissions_for(channel.guild.me)
            if perms.read_messages == False:
                continue

            res = self.cur.execute(f"select * from channels where id={channel.id}")
            if not res.fetchone():
                self.cur.execute(f"insert into channels values({channel.id}, '{channel.name}')")
                self.con.commit()

            num_messages = 0
            print(channel)
            async for message in channel.history(limit=None, oldest_first=True):
                num_messages += 1
                await insert_message(message, self.cur, self.con)

            await ctx.channel.send(f"{channel.name}-{num_messages}")

        await ctx.reply(f"Complete.")

    @commands.command()
    async def query(self, ctx, *, arg):
        if not is_owner(ctx.author.id):
            await ctx.reply("You are not in the sudoers file.  This incident will be reported.")
            return

        qcon = sqlite3.connect("file:messages.db?mode=ro", uri=True)
        qcur = self.con.cursor()
        arg = arg.strip()
        if arg[0] == arg[-1] and arg[0] == '`':
            arg = arg[1:-1]
        res = qcur.execute(arg)
        ret = res.fetchall()
        if ret == []:
            await ctx.reply("No results")
        else:
            if len(f'{ret}') > 2000:
                await ctx.reply("Results too long")
            else:
                await ctx.reply(ret)

    @commands.command()
    async def reload(self, ctx, module):
        await self.bot.reload_extension(f"modules.{module}")
        await ctx.reply(f"{module} successfully reloaded")

def is_owner(author):
    return author == int(settings.get()["owner"])

async def insert_message(ctx, cur, con):
    res = cur.execute(f"select content, revision from messages where id={ctx.id} order by revision desc")
    results = res.fetchone()

    # Insert if doesn't exist in db or the content is different
    if not results or ctx.content.replace("'", "''") != results[0]:
        revision = (results[1] + 1) if results else 0

        timestamp = ctx.created_at.timestamp()

        if ctx.edited_at and revision > 0:
            # This is to use the original sending timestamp if the message doesn't
            # exist in the database yet (e.g. fbackup or a raw_message event)
            timestamp = ctx.edited_at.timestamp()

        cur.execute("insert into messages values "
                    + f"({ctx.id},"
                    + f"{ctx.author.id},"
                    + f"{ctx.guild.id},"
                    + f"{ctx.channel.id},"
                    + f"'{timestamp}',"
                    + f"'0',"
                    + f"'" + ctx.content.replace("'", "''") + "',"
                    + f"{revision}"
                    + ")")
        con.commit()
    else:
        # No edit performed on ctx.content, probably an embed change
        pass

    # We still want to look at attachments regardless of if the message already exists
    for a in ctx.attachments:
        got = False
        data = None

        res = cur.execute(f"select * from blobs where id={a.id}")
        if not res.fetchone():
            tries = 3
            while tries > 0:
                for cached in [False, True]:
                    try:
                        data = await a.read(use_cached=cached)
                        got = True
                        break
                    except discord.HTTPException:
                        await ctx.channel.send("HTTPException while saving blob {a.id}")
                    except discord.Forbidden:
                        await ctx.channel.send("Forbidden while saving blob {a.id}")
                    except discord.NotFound:
                        await ctx.channel.send("NotFound while saving blob, was it deleted? {a.id}")

                if got:
                    break
                tries -= 1
            if tries == 0:
                await ctx.channel.send("Failed on blob {a.id}")
                continue


            cur.execute("insert into blobs values (?, ?, ?, ?)",
                        (a.id, ctx.id, a.filename, sqlite3.Binary(data)))
            con.commit()


async def setup(client):
    await client.add_cog(BotStuff(client))
