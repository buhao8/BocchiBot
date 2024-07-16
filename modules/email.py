import requests
import settings

async def exec(client, msg, args):
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
