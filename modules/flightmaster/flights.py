import httpx
import json
from pprint import pprint
import calendar

# data = json.loads(request.text)
with open('response.json', 'r') as f:
    data = json.load(f)

# pprint(data)
# with open('response.json', 'w') as f:
#     json.dump(data, f, indent=4)


def get_month(year, month):
    ret = []
    weeks = data["calendarMonths"][0]["weeks"]
    for w in weeks:
        week = w["days"]
        for day in week:
            if day["solution"] != None:
                ret.append(day["date"])
                #print(day["date"])
    return ret

async def get_cal(year, month, origin, dest, cabin):

    cabins = {
        'ANY': '',
        'Y': 'COACH',
        'PY': 'PREMIUM_COACH',
        'J': 'BUSINESS,FIRST',
        'F': 'FIRST'
    }

    r_headers = {
        'Content-Type': 'application/json',
        'Origin': 'https://www.aa.com',
        'Referer': 'https://www.aa.com/booking/choose-flights/1',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0'
    }


    r_json = {
        'loyaltyInfo': None,
        'metadata': {
            'selectedProducts': [],
            'tripType': 'OneWay',
            'udo': {}
        },
        'passengers': [
            {
                'count': 1,
                'type': 'adult'
            }
        ],
        'queryParams': {
            'sessionId': '',
            'sliceIndex': 0,
            'solutionId': '',
            'solutionSet': ''
        },
        'requestHeader': {
            'clientId': 'AAcom'
        },
        'slices': [
            {
                'allCarriers': True,
                'cabin': cabins[cabin],
                'departureDate': f'{year}-{month:0>2}-{calendar.monthrange(year,month)[1]}',
                'destination': dest,
                'destinationNearbyAirports': False,
                'maxStops': 0,
                'origin': origin,
                'originNearbyAirports': False
            }
        ],
        'tripOptions': {
            'corporateBooking': False,
            'fareType': 'Lowest',
            'locale': 'en_US',
            'pointOfSale': None,
            'searchType': 'Award'
        },
        'version': ''
    }

    async with httpx.AsyncClient() as client:
        response = await client.post('https://www.aa.com/booking/api/search/calendar', headers=r_headers, json=r_json, timeout=None)
    #print("elapsed time:", response.elapsed.total_seconds())
    if response.status_code != 200:
        print("=============== ERROR =============== ")
        print(response.text)
        print("===================================== ")
    return response
