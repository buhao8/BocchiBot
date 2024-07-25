import discord
from discord.ext import commands, tasks
import requests
import settings
import sqlite3
import json
import asyncio
import traceback
import io

from modules.flightmaster import flights as flights

class FlightsError(Exception):
    def __init__(self, message, error):
        super().__init__(message)
        self.error = error

    def __str__(self):
        if hasattr(self.error, 'status_code'):
            return (f"\n\nstatus_code: {self.error.status_code}"
                  + f"\n\nresponse: {self.error.text}")
        return f"\n\nresponse: {self.error}"

class FlightUser():
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.email = data["email"]
        self.phone = data["phone"]

class FlightData():
    def __init__(self, data):
        self.uid = data["user_id"]
        self.year = data["year"]
        self.month = data["month"]
        self.day = data["day"]
        self.origin = data["origin"]
        self.dest = data["dest"]
        self.cabin = data["cabin"]
        self.stops = data["stops"] if "stops" in data else 0
        self.airline = data["airline"] if "airline" in data else "AA"

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
        self.check_alerts.cancel()


    async def email(self, receiver, subject, text):
        requests.post('https://api.mailgun.net/v3/buhao.jp/messages',
                      auth=('api', settings.get()["tokens"]["mailgun"]),
                      data={'from': 'FlightMaster <flightmaster@buhao.jp>',
                            'to': [receiver],
                            'subject': subject,
                            'text': text,
                           })

    async def _get_cal(self, flight: FlightData):
        try:
            full_response = await flights.get_cal(flight.year, flight.month, flight.origin, flight.dest, flight.cabin)
            resp = json.loads(full_response.text)

            if len(resp['calendarMonths']) == 0:
                return []

            ret = []
            weeks = resp['calendarMonths'][0]['weeks']
            for week in weeks:
                days = week['days']
                for day in days:
                    if day['solution']:
                        ret.append(day)
            return ret
        except Exception as e:
            raise FlightsError(e, full_response)



    @commands.Cog.listener()
    async def on_ready(self):
        self.check_alerts.start()
        print("READY flightmaster")


    @tasks.loop(seconds=120.0)
    async def check_alerts(self):
        res = self.cur.execute("select user_id, year, month, day, origin, dest, cabin from flights group by month, year, origin, dest, cabin")
        data_to_query = res.fetchall()

        res = self.cur.execute("select id, name, email, phone from users")
        users = res.fetchall()

        dates = []

        channel = self.bot.get_channel(int(self.flight_channel))

        for monthyear in data_to_query:
            flight = FlightData(monthyear)
            try:
                ret = await self._get_cal(flight)
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
                    'dom': solution['dayOfMonth'],
                    'month': flight.month,
                    'year': flight.year,
                    'origin': flight.origin,
                    'dest': flight.dest,
                    'cabin': flight.cabin
                })
            await asyncio.sleep(3)

        for user in users:
            u = FlightUser(user)
            res = self.cur.execute(f"select user_id, year, month, day, origin, dest, cabin from flights where user_id={u.id}")
            results = res.fetchall()

            body = ""

            for result in results:
                r = FlightData(result)

                for date in dates:
                    if date['month'] == r.month and date['year'] == r.year and date['origin'] == r.origin and date['dest'] == r.dest and date['cabin'] == r.cabin:
                        body += f"Flight found for {r.origin}->{r.dest} on {r.month:0>2}-{date['dom']:0>2}-{r.year} in {r.cabin}\n"

            if body != "":
                for address in [u.phone, u.email]:
                    subject = "Flight Found!"
                    if address != "":
                        #await self.email(address, subject, body)
                        pass
                await channel.send(f"<@{u.id}> {subject}\n{body}")


    @commands.command()
    async def create_alert(self, ctx, origin: str, dest: str, cabin: str, year: int, month: int):
        # check if user exists
        res = self.cur.execute(f"select * from users where id={ctx.author.id}")
        result = res.fetchone()
        if not result:
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()

        # check if alert for these params exists for user
        q = f"""
            select * from flights
                where user_id={ctx.author.id}
                and year={year}
                and month={month}
                and cabin='{cabin}'
                and origin='{origin}'
                and dest='{dest}'
            """

        res = self.cur.execute(q)
        result = res.fetchone()
        if result:
            await ctx.reply(f"You already have an alert for {origin}->{dest} on {month:0>2}-{year} in {cabin}")
        else:
            self.cur.execute("insert into flights values (?,?,?,?,?,?,?,?,?)",
                             (ctx.author.id, year, month, 0, origin, dest, cabin, 0, "AA"))
            self.con.commit()
            await ctx.reply(f"Created alert for {origin}->{dest} on {month:0>2}-{year} in {cabin}")

    @commands.command()
    async def delete_alert(self, ctx, origin: str, dest: str, cabin: str, year: int, month: int):
        origin = origin.upper()
        dest = dest.upper()
        cabin = cabin.upper()

        q = f"""
            delete from flights
                where user_id={ctx.author.id}
                and year={year}
                and month={month}
                and cabin='{cabin}'
                and origin='{origin}'
                and dest='{dest}'
            """
        self.cur.execute(q)
        self.con.commit()
        await ctx.reply("Sent delete request to database")

    @commands.command()
    async def all_alerts(self, ctx):
        res = self.cur.execute(f"select id, name from users")
        users = res.fetchall()

        ret = "All alerts:\n"
        for user in users:
            res = self.cur.execute(f"select year, month, origin, dest, cabin from flights where user_id={user[0]} order by year, month")
            results = res.fetchall()

            if len(results) > 0:
                ret += f"{user[1]}\n"

            for result in results:
                (year, month, origin, dest, cabin) = result
                ret += f"\t\\- {origin}->{dest} on {year}-{month:0>2} in {cabin}\n"

        await ctx.reply(ret)

    @commands.command()
    async def current_alerts(self, ctx):
        res = self.cur.execute(f"select year, month, origin, dest, cabin from flights where user_id={ctx.author.id}")
        results = res.fetchall()

        ret = "Current alerts:\n"
        for result in results:
            (year, month, origin, dest, cabin) = result
            ret += f"\t\\- {origin}->{dest} on {month:0>2}-{year} in {cabin}\n"

        await ctx.reply(ret)

    @commands.command()
    async def get_cal(self, ctx, origin: str, dest: str, cabin: str, year: int, month: int):
        ret = await self._get_cal(FlightData(-1, year, month, 32, origin, dest, cabin))
        if ret:
            msg = json.dumps(ret, indent=4)
            if len(msg) > 2000:
                buf = io.StringIO(msg)
                f = discord.File(buf, filename="err_msg.txt")
                await ctx.reply(file=f)
            else:
                await ctx.reply(msg)
            return
        else:
            await ctx.reply("no flight, get rekt")


async def setup(client):
    await client.add_cog(FlightMaster(client))
