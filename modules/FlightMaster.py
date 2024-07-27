import discord
from discord.ext import commands, tasks
import datetime
from dateutil.parser import parse
import requests
import settings
import sqlite3
import json
import asyncio
import traceback
import io

from modules.flightmaster.vaflights import get_results as get_va_results, get_query as get_va_query
from modules.flightmaster.aaflights import get_results as get_aa_results, get_query as get_aa_query
from modules.flightmaster.flightdata import FlightData, FlightUser, FlightsError

class FlightMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.con = sqlite3.connect("flights.db")
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
        with open('settings.json') as f:
            data = json.load(f)
            self.flight_mgmt = data["flight_mgmt"]
            self.flight_channel = data["flight_channel"]

    def cog_unload(self):
        self.check_alerts("AA").cancel()
        self.check_alerts("VA").cancel()


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
        self.aa_loop.start()
        self.va_loop.start()
        print("READY flightmaster")

    async def check_alerts(self, airline: str, get_results, get_query):

        res = self.cur.execute(get_query())

        data_to_query = res.fetchall()

        res = self.cur.execute("select id, name, email, phone from users")
        users = res.fetchall()

        dates = []

        channel = self.bot.get_channel(int(self.flight_channel))

        for query in data_to_query:
            flight = FlightData(query)
            try:
                ret = await get_results(flight)
            except FlightsError as e:
                mgmt_pings = ""
                for member in self.flight_mgmt:
                    mgmt_pings += f"<@{member}> "
                err_pings = f"{mgmt_pings} FLIGHTMASTER ERROR!!!\n"
                err_msg = f"```{traceback.format_exc()}```"

                if len(err_pings + err_msg) > 2000:
                    buf = io.StringIO(err_msg)
                    f = discord.File(buf, filename="err_msg.txt")
                    await channel.send(err_pings, file=f)
                else:
                    print(err_pings + err_msg)
                    await channel.send(err_pings + err_msg)
                return

            for solution in ret:
                dates.append({
                    'day': int(solution.day),
                    'month': flight.month,
                    'year': flight.year,
                    'origin': flight.origin,
                    'dest': flight.dest,
                    'cabin': flight.cabin
                })
            await asyncio.sleep(3)

        for user in users:
            u = FlightUser(user)
            res = self.cur.execute(f"select user_id, year, month, day, origin, dest, cabin from flights where user_id={u.id} and airline='{airline}' order by origin, dest, year, month")

            results = res.fetchall()

            body = ""

            for result in results:
                r = FlightData(result)

                for date in dates:
                    if date['day'] == r.day and date['month'] == r.month and date['year'] == r.year and date['origin'] == r.origin and date['dest'] == r.dest and date['cabin'] == r.cabin:
                        body += f"Flight found for {r.origin}->{r.dest} on {r.month:0>2}-{date['day']:0>2}-{r.year} in {r.cabin} for {airline}\n"

            if body != "":
                for address in [u.phone, u.email]:
                    subject = "Flight Found!"
                    if address != "":
                        #await self.email(address, subject, body)
                        pass
                await channel.send(f"<@{u.id}> {subject}\n{body}")

    @tasks.loop(seconds=60)
    async def aa_loop(self):
        await self.check_alerts('AA', get_aa_results, get_aa_query)

    @tasks.loop(seconds=60)
    async def va_loop(self):
        await self.check_alerts('VA', get_va_results, get_va_query)

    @commands.command()
    async def create_alert(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        airlines = ['AA', 'VA']
        # check if user exists
        res = self.cur.execute(f"select * from users where id={ctx.author.id}")

        result = res.fetchone()

        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()
        airline = airline.upper()

        if not result:
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return
        if airline not in airlines:
            await ctx.reply("THIS AIRLINE IS NOT CURRENTLY SUPPORTED")
            return
        if airline == 'VA' and cabin != 'F':
            await ctx.reply("THIS CABIN IS NOT CURRENTLY SUPPORTED FOR VA")
            return

        #TODO fix exception handling for improper date strings
        try:
            start = parse(startdate)
            end = parse(enddate)
        except:
            print("invalid date formats")

        if start < datetime.datetime.today():
            await ctx.reply("Start date is in the past REEEEEE")
            return
        if end < start:
            await ctx.reply("invalid range!!")
            return
        if end > datetime.datetime.today() + datetime.timedelta(days=365):
            await ctx.reply("your range is too large!!")
            return

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

    @commands.command()
    async def delete_alert(self, ctx, origin: str, dest: str, cabin: str, startdate: str, enddate: str, airline: str):
        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()
        airline = airline.upper()

        #TODO add error handling for improper date input
        try:
            start = parse(startdate)
            end = parse(enddate)
        except:
            print("invalid date formats")
        gap = end - start
        if gap.days > 365:
            await ctx.reply("Your range is TOO LARGE")
            return
        if end < start:
            await ctx.reply("invalid range!!")
            return
        if end > datetime.datetime.today() + datetime.timedelta(days=365):
            await ctx.reply("your range is too large!!")
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
    async def all_alerts(self, ctx):
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

    @commands.command()
    async def get_aa_month(self, ctx, origin: str, dest: str, cabin: str, monthyear: str):
        try:
            d = parse(monthyear)
        except:
            print("invalid date format")
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
        ret = await get_aa_results(FlightData(data))
        if ret:
            days = []
            for solution in ret:
                days.append(int(solution.day))
                msg = f"Flights found for {origin}->{dest} on {d.month}-{d.year} on days {days} in {cabin} for AA"
            if len(msg) > 2000:
                buf = io.StringIO(msg)
                f = discord.File(buf, filename="err_msg.txt")
                await ctx.reply(file=f)
            else:
                await ctx.reply(msg)
            return
        else:
            await ctx.reply(f"get rekt, no flights found for {origin}->{dest} on {d.month}-{d.year} in {cabin}")

    @commands.command()
    async def get_va_day(self, ctx, origin:str, dest:str, cabin:str, date: str):
        try:
            d = parse(date)
        except:
            print("invalid date format")
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
        ret = await get_va_results(FlightData(data))
        if ret:
            msg = f"Flight found for {origin}->{dest} on {d.date()} in {cabin} for VA\n"
            if len(msg) > 2000:
                buf = io.StringIO(msg)
                f = discord.File(buf, filename="err_msg.txt")
                await ctx.reply(file=f)
            else:
                await ctx.reply(msg)
            return
        else:
            await ctx.reply(f"get rekt, no flights found for {origin}->{dest} on {d.date()} in {cabin}")

async def setup(client):
    await client.add_cog(FlightMaster(client))
