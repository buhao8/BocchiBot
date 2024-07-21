import discord
from discord.ext import commands, tasks
import requests
import settings
import sqlite3
import json
import asyncio
import traceback
import io

import flights

class FlightsError(Exception):
    def __init__(self, message, error):
        super().__init__(message)
        self.error = error

    def __str__(self):
        return (f"\n\nstatus_code: {self.error.status_code}\n"
              + f"response: {self.error.text}")


class FlightMaster(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.con = sqlite3.connect("flights.db")
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

    async def _get_cal(self, origin: str, dest: str, cabin: str, year: int, month: int):
        try:
            full_response = flights.get_cal(year, month, origin, dest, cabin)
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
        except KeyError as e:
            raise FlightsError(e, full_response)



    @commands.Cog.listener()
    async def on_ready(self):
        self.check_alerts.start()
        print("READY flightmaster")


    @tasks.loop(seconds=60.0)
    async def check_alerts(self):
        res = self.cur.execute("select user_id, year, month, origin, dest, cabin from flights group by month, year, origin, dest, cabin")
        data_to_query = res.fetchall()

        res = self.cur.execute("select * from users")
        users = res.fetchall()

        dates = []

        channel = self.bot.get_channel(int(self.flight_channel))

        for monthyear in data_to_query:
            (user_id, year, month, origin, dest, cabin) = monthyear
            try:
                ret = await self._get_cal(origin, dest, cabin, year, month)
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
                    await channel.send(err_pings + err_msg)
                return

            #print("requesting", origin, dest, cabin, year, month)

            for solution in ret:
                dates.append({
                    'dom': solution['dayOfMonth'],
                    'month': month,
                    'year': year,
                    'origin': origin,
                    'dest': dest,
                    'cabin': cabin
                })
            await asyncio.sleep(2)

        for user in users:
            (uid, name, email, phone) = user
            res = self.cur.execute(f"select user_id, year, month, origin, dest, cabin from flights where user_id={uid}")
            results = res.fetchall()

            body = ""

            for result in results:
                (uid, uyear, umonth, uorigin, udest, ucabin) = result

                for date in dates:
                    if date['month'] == umonth and date['year'] == uyear and date['origin'] == uorigin and date['dest'] == udest and date['cabin'] == ucabin:
                        body += f"Flight found for {uorigin}->{udest} on {umonth:0>2}-{date['dom']}-{uyear} in {ucabin}\n"

            if body != "":
                for address in [phone, email]:
                    subject = "Flight Found!"
                    if address != "":
                        await self.email(address, subject, body)
                await channel.send(f"<@{uid}> {subject}\n{body}")


    @commands.command()
    async def create_alert(self, ctx, origin: str, dest: str, cabin: str, year: int, month: int):
        # check if user exists
        res = self.cur.execute(f"select * from users where id={ctx.author.id}")
        result = res.fetchone()
        if not result:
            await ctx.reply("You are not in the list of authorized users.  This incident will be reported.")
            return

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
        ret = self._get_cal(self, origin, dest, cabin, year, month)
        if ret:
            await ctx.reply(json.dumps(ret, indent=4))
        else:
            await ctx.reply("no flight, get rekt")


async def setup(client):
    reef = FlightMaster(client)
    await client.add_cog(reef)
