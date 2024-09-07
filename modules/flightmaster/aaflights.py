import httpx
import json
from pprint import pprint
from copy import deepcopy
import calendar
from modules.flightmaster import airline
from modules.flightmaster.flightdata import FlightData, FlightsError

class AA(airline.Airline):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return "AA"

    def is_valid_alert(self, origin: str, dest: str, cabin: str):
        return cabin in self.cabin_map().keys()

    def cabin_map(self):
        cabins = {
            'ANY': '',
            'Y': 'COACH',
            'PY': 'PREMIUM_COACH',
            'J': 'BUSINESS,FIRST',
            'F': 'FIRST'
        }
        return cabins


    def get_query(self):
        return "select user_id, year, month, origin, dest, cabin, airline from flights where airline = 'AA' group by year, month, origin, dest, cabin"

    def get_delay(self):
        return 3

    def get_link_to_flight(self, flight: FlightData):
        return f'https://www.aa.com/booking/search?locale=en_US&pax=1&adult=1&type=OneWay&searchType=Award&cabin={self.cabin_map()[flight.cabin]}&carriers=ALL&travelType=personal&slices=%5B%7B%22orig%22:%22{flight.origin}%22,%22origNearby%22:false,%22dest%22:%22{flight.dest}%22,%22destNearby%22:false,%22date%22:%22{flight.year}-{flight.month:0>2}-{flight.day:0>2}%22%7D%5D'

    async def get_results(self, flight: FlightData):
        #print(f'looking for {flight.month}/{flight.day}/{flight.year} from {flight.origin} to {flight.dest} in cabin {flight.cabin} using AMERICAN AIRLINES')
        try:
            full_response = await self.get_cal(flight.year, flight.month, flight.origin, flight.dest, flight.cabin)
            resp = json.loads(full_response.text)

            if len(resp['calendarMonths']) == 0:
                return []

            ret = []
            weeks = resp['calendarMonths'][0]['weeks']
            for week in weeks:
                days = week['days']
                for day in days:
                    if day['solution']:
                        solution = deepcopy(flight)
                        solution.day = day['dayOfMonth']
                        ret.append(solution)
            return ret
        except Exception as e:
            raise FlightsError(e, full_response)


    async def get_cal(self, year, month, origin, dest, cabin):

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
                    'cabin': self.cabin_map()[cabin],
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

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post('https://www.aa.com/booking/api/search/calendar', headers=r_headers, json=r_json, timeout=None)
        except:
            return "httpx.AsyncClient().post exception"
        #print("elapsed time:", response.elapsed.total_seconds())
        if response.status_code != 200:
            print("=============== ERROR =============== ")
            print(response.text)
            print("===================================== ")
        return response
