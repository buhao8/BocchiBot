import discord
from discord.ext import commands, tasks
import asyncio
import datetime
import dateutil.parser
import settings
import io
import json
import requests
import sqlite3
import time
import traceback

from modules.flightmaster import airline, aaflights, vaflights
from modules.flightmaster.flightdata import FlightData, FlightUser, FlightsError

class FlightMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.con = sqlite3.connect("flights.db")
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()

        config = settings.get()["flightmaster"]
        self.flight_mgmt = config["flight_mgmt"]
        self.flight_channel = config["flight_channel"]
        self.flight_errors = config["flight_errors"]

        self.disables = []
        self.airlines = [aaflights.AA(), vaflights.VA()]
        print(f"flightmaster ctor (is_ready = {self.bot.is_ready()})")
        if self.bot.is_ready():
            self.check_loop.cancel()
            self.check_loop.start()

    def cog_unload(self):
        print("UNLOAD flightmaster")
        self.check_loop.cancel()

    async def email(self, receiver, subject, text):
        requests.post('https://api.mailgun.net/v3/buhao.jp/messages',
                      auth=('api', settings.get()["tokens"]["mailgun"]),
                      data={'from': 'FlightMaster <flightmaster@buhao.jp>',
                            'to': [receiver],
                            'subject': subject,
                            'text': text,
                           })

    @commands.Cog.listener()
    async def on_ready(self):
        # Doesn't get called on cog/extension reload
        print("READY flightmaster")
        print("on_ready = " + str(self.bot.is_ready()))
        print(f"flightmaster on_ready (is_ready = {self.bot.is_ready()})")
        if self.bot.is_ready():
            self.check_loop.cancel()
            self.check_loop.start()

    @tasks.loop(seconds=15)
    async def check_loop(self):
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=now))
        tasks = [self.check_alerts(airline) for airline in self.airlines]

        # Should never reach here
        await asyncio.gather(*tasks)

    async def check_alerts(self, airline):
        while True:
            await asyncio.sleep(15)

            #print(f"Status of {airline}: {'Disabled' if str(airline) in self.disables else 'Enabled'}")

            now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=now))

            # Each thread needs its own connection
            db_con = sqlite3.connect("flights.db")
            db_con.row_factory = sqlite3.Row
            db_cur = db_con.cursor()

            channel = self.bot.get_channel(int(self.flight_channel))

            res = db_cur.execute(airline.get_query())
            data_to_query = res.fetchall()

            res = db_cur.execute("select id, name, email, phone from users")
            users = res.fetchall()

            for query in data_to_query:
                # Break out if we're disabled now, but still flush gotten alerts
                if str(airline).upper() in self.disables:
                    print(f"{airline} is disabled")
                    break

                flight = FlightData(query)
                try:
                    ret = await airline.get_results(flight)
                except FlightsError as e:
                    err_msg = f"```{flight}\n\n{traceback.format_exc()}```"
                    await self.send_error(pings=True, title="FLIGHTMASTER ERROR!!!", content=err_msg)
                    await asyncio.sleep(airline.get_delay())
                    continue

                dates = []

                for solution in ret:
                    dates.append({
                        'day': int(solution.day),
                        'month': flight.month,
                        'year': flight.year,
                        'origin': flight.origin,
                        'dest': flight.dest,
                        'cabin': flight.cabin
                    })

                for user in users:
                    u = FlightUser(user)
                    res = db_cur.execute(f"""
                        select user_id, year, month, day, origin, dest, cabin
                            from flights
                                where user_id={u.id} and airline='{airline}'
                                    order by origin, dest, year, month""")

                    results = res.fetchall()

                    body = ""
                    subject = "Flight Found!"

                    for result in results:
                        r = FlightData(result)

                        for date in dates:
                            if (date['day'] == r.day and
                                date['month'] == r.month and
                                date['year'] == r.year and
                                date['origin'] == r.origin and
                                date['dest'] == r.dest and
                                date['cabin'] == r.cabin):

                                link = airline.get_link_to_flight(r)
                                body += f"[Flight found for]({link}) {r.origin}->{r.dest} on {r.month:0>2}-{date['day']:0>2}-{r.year} in {r.cabin} for {airline}\n"

                                if len(body) > 1500:
                                    await channel.send(f"<@{u.id}> {subject}\n{body}")
                                    body = ""

                    if body != "":
                        for address in [u.phone, u.email]:
                            if address != "":
                                #await self.email(address, subject, body)
                                pass
                        await channel.send(f"<@{u.id}> {subject}\n{body}")

                await asyncio.sleep(airline.get_delay())

            db_con.close()

    @commands.command(hidden=True)
    async def create_alert(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        await self.create_alerts(ctx, origin, dest, cabin, startdate, enddate, airline)

    @commands.command()
    async def create_alerts(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        # check if user exists

        origins = origin.upper().split(",")
        dests = dest.upper().split(",")
        cabin = cabin.upper()
        airlines = airline.upper().split(",")

        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        supported_airlines = {str(airline): airline for airline in self.airlines}

        for airline in airlines:
            if airline not in supported_airlines:
                await ctx.reply("THIS AIRLINE IS NOT CURRENTLY SUPPORTED")
                return
            if not supported_airlines[airline].is_valid_alert(cabin):
                await ctx.reply(f"CABIN {cabin} IS NOT CURRENTLY SUPPORTED FOR {airline}")
                return

        try:
            start = dateutil.parser.parse(startdate)
            end = dateutil.parser.parse(enddate)
        except:
            await ctx.reply("Invalid date format(s)")
            return

        if start < datetime.datetime.today():
            await ctx.reply("Start date is in the past REEEEEE")
            return
        if end < start:
            await ctx.reply("End date is before start date, are you waiting for time integer overflow?????")
            return
        if end > datetime.datetime.today() + datetime.timedelta(days=365):
            await ctx.reply("Your range is too large, why you planning so early?")
            return

        for origin in origins:
            for dest in dests:
                for airline in airlines:
                    date = start
                    while date <= end:
                        q = f"""
                            select * from flights
                                where user_id={ctx.author.id}
                                and year={date.year}
                                and month={date.month}
                                and day = {date.day}
                                and cabin='{cabin}'
                                and origin='{origin}'
                                and dest='{dest}'
                                and airline = '{airline}'
                            """
                        res = self.cur.execute(q)
                        result = res.fetchone()
                        if result:
                            await ctx.reply(f"You already have an alert for {origin}->{dest} on {date} in {cabin} for {airline}")
                        else:
                            self.cur.execute("insert into flights values (?,?,?,?,?,?,?,?,?)",
                                            (ctx.author.id, date.year, date.month, date.day, origin, dest, cabin, 0, airline))
                            self.con.commit()
                        date = date + datetime.timedelta(days = 1)
                    await ctx.reply(f"Created alert for {origin}->{dest} from {start.date()} to {end.date()} in {cabin} for {airline}")

    @commands.command(hidden=True)
    async def delete_alert(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        await self.delete_alerts(ctx, origin, dest, cabin, startdate, enddate, airline)

    @commands.command()
    async def delete_alerts(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()
        airline = airline.upper()

        res = self.cur.execute(f"select * from users where id={ctx.author.id}")
        result = res.fetchone()

        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        try:
            start = dateutil.parser.parse(startdate)
            end = dateutil.parser.parse(enddate)
        except:
            await ctx.reply("Invalid date format(s)")
            return

        gap = end - start
        if gap.days > 365:
            await ctx.reply("Your range is TOO LARGE")
            return
        if end < start:
            await ctx.reply("Invalid range!!")
            return
        if end > datetime.datetime.today() + datetime.timedelta(days=365):
            await ctx.reply("Your range is too large!!")
            return

        date = start
        while date <= end:
            q = f"""
            delete from flights
                where user_id={ctx.author.id}
                and year={date.year}
                and month={date.month}
                and day = {date.day}
                and cabin='{cabin}'
                and origin='{origin}'
                and dest='{dest}'
                and airline = '{airline}'
            """
            self.cur.execute(q)
            self.con.commit()
            date = date + datetime.timedelta(days = 1)
        await ctx.reply("Sent delete requests to database")

    @commands.command()
    async def delete_all_alerts(self, ctx, startdate: str, enddate: str):

        res = self.cur.execute(f"select * from users where id={ctx.author.id}")
        result = res.fetchone()

        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        try:
            start = dateutil.parser.parse(startdate)
            end = dateutil.parser.parse(enddate)
        except:
            await ctx.reply("Invalid date format(s)")
            return

        gap = end - start
        if gap.days > 365:
            await ctx.reply("Your range is TOO LARGE")
            return
        if end < start:
            await ctx.reply("Invalid range!!")
            return
        if end > datetime.datetime.today() + datetime.timedelta(days=365):
            await ctx.reply("Your range is too large!!")
            return

        date = start
        while date <= end:
            q = f"""
            delete from flights
                where user_id={ctx.author.id}
                and year={date.year}
                and month={date.month}
                and day = {date.day}
            """
            self.cur.execute(q)
            self.con.commit()
            date = date + datetime.timedelta(days = 1)
        await ctx.reply("Sent delete requests to database")

    @commands.command()
    async def all_alerts(self, ctx):
        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        res = self.cur.execute(f"select id, name from users")
        users = res.fetchall()

        ret = "All alerts:\n"
        for user in users:
            res = self.cur.execute(f"select year, month, day, origin, dest, cabin, airline from flights where user_id={user[0]} order by year, month, day, origin, dest, airline, cabin")
            results = res.fetchall()

            if len(results) > 0:
                ret += f"{user[1]}\n"

            for result in results:
                flight = FlightData(result)
                ret += f"\t\\- {flight.origin}->{flight.dest} on {flight.month:0>2}-{flight.day:0>2}-{flight.year} in {flight.cabin} for {flight.airline}\n"

        if len(ret) > 2000:
            buf = io.StringIO(ret)
            f = discord.File(buf, filename="all_alerts.txt")
            await ctx.reply(file = f)
        else:
            await ctx.reply(ret)

    @commands.command()
    async def current_alerts(self, ctx):
        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        res = self.cur.execute(f"select year, month, day, origin, dest, cabin, airline from flights where user_id={ctx.author.id} order by year, month, day, origin, dest, airline, cabin")
        results = res.fetchall()

        ret = "Current alerts:\n"
        for result in results:
            flight = FlightData(result)
            ret += f"\t\\- {flight.origin}->{flight.dest} on {flight.month:0>2}-{flight.day:0>2}-{flight.year} in {flight.cabin} for {flight.airline}\n"
        if len(ret) > 2000:
            buf = io.StringIO(ret)
            f = discord.File(buf, filename="current_alerts.txt")
            await ctx.reply(file = f)
        else:
            await ctx.reply(ret)

        await ctx.reply("See more at https://flights.buhao.jp/")

    @commands.command()
    async def get_aa_month(self, ctx, origin: str, dest: str, cabin: str, monthyear: str):
        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        try:
            d = dateutil.parser.parse(monthyear)
        except:
            await ctx.reply("Invalid date format")
            return
        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()
        data = {
            "year" : d.year,
            "month": d.month,
            "origin": origin,
            "dest": dest,
            "cabin": cabin
        }
        ret = await aaflights.AA().get_results(FlightData(data))
        if ret:
            days = []
            for solution in ret:
                days.append(int(solution.day))

                data["day"] = int(solution.day)
                flight = FlightData(data)
                link = aaflights.AA().get_link_to_flight(flight)
                #await ctx.reply(f"[Flight found]({link}) for {origin}->{dest} on {d.month:0>2}-{solution.day:0>2}-{d.year} in {cabin} for AA")

            msg = f"Flights found for {origin}->{dest} on {d.month:0>2}-{d.year} on days {days} in {cabin} for AA"

            await ctx.reply(msg)
        else:
            await ctx.reply(f"get rekt, no flights found for {origin}->{dest} on {d.month:0>2}-{d.year} in {cabin}")

    @commands.command()
    async def get_va_day(self, ctx, origin: str, dest: str, cabin: str, date: str):
        if not self.check_auth(ctx.author.id):
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        try:
            d = dateutil.parser.parse(date)
        except:
            await ctx.reply("Invalid date format")
            return
        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()
        data = {
            "year" : d.year,
            "month": d.month,
            "day" : d.day,
            "origin": origin,
            "dest": dest,
            "cabin": cabin
        }
        ret = await vaflights.VA().get_results(FlightData(data))
        if ret:
            #link = vaflights.VA().get_link_to_flight(FlightData(data))
            #msg = f"[Flight found for]({link}) {origin}->{dest} on {d.month:0>2}-{d.day:0>2}-{d.year} in {cabin} for VA\n"
            msg = f"Flight found for {origin}->{dest} on {d.month:0>2}-{d.day:0>2}-{d.year} in {cabin} for VA\n"
            if len(msg) > 2000:
                buf = io.StringIO(msg)
                f = discord.File(buf, filename="err_msg.txt")
                await ctx.reply(file=f)
            else:
                await ctx.reply(msg)
            return
        else:
            await ctx.reply(f"get rekt, no flights found for {origin}->{dest} on {d.month:0>2}-{d.day:0>2}-{d.year} in {cabin}")

    @commands.command()
    async def toggle_airline(self, ctx, airline: str):
        if airline.upper() in self.disables:
            self.disables.remove(airline.upper())
            await ctx.reply(f"Enabled {airline.upper()}")
        elif airline.upper() in [str(a) for a in self.airlines]:
            self.disables.append(airline.upper())
            await ctx.reply(f"Disabled {airline.upper()}")
        else:
            await ctx.reply(f"Airline doesn't exist")

    @commands.command()
    async def prune_errors(self, ctx):
        if ctx.author.id != int(settings.get()["owner"]):
            await ctx.reply("You are not in the sudoers file.  This incident will be reported.")
            return

        counter = 0
        messages = [message async for message in ctx.channel.history(limit=5000, after=datetime.datetime(2024, 7, 30))]
        for message in messages:
            if message.author == self.bot.user:
                if "FLIGHTMASTER" in message.content:
                    counter += 1
                    await message.delete()
                    await asyncio.sleep(1)
        await ctx.reply(f"ARMAGEDDON COMPLETE!!! Deleted {counter} FlightMaster Error messages")


    def check_auth(self, author):
        res = self.cur.execute(f"select * from users where id={author}")
        result = res.fetchone()
        return result

    async def send_error(self, pings=False, title="", content=""):
        mgmt_pings = ''.join([f"<@{member}> " for member in self.flight_mgmt]) if pings else ''
        err_pings = mgmt_pings + title + "\n"

        channel = self.bot.get_channel(int(self.flight_errors))

        if "Too Many Requests Processing" in content:
            await channel.send(err_pings + "Too Many Requests Processing")
            return

        if len(err_pings + content) > 2000:
            buf = io.StringIO(content)
            f = discord.File(buf, filename="err_msg.txt")
            await channel.send(err_pings, file=f)
        else:
            await channel.send(err_pings + content)

async def setup(client):
    print("Setup flightmaster")
    await client.add_cog(FlightMaster(client))
