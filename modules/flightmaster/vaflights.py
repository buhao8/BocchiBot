import httpx
from pprint import pprint
import json
from modules.flightmaster import airline
from modules.flightmaster.flightdata import FlightData, FlightsError

class VA(airline.Airline):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return "VA"

    def is_valid_alert(self, origin: str, dest: str, cabin: str):
        return cabin in ['F']

    def get_query(self):
        return "select user_id, year, month, day, origin, dest, cabin, airline from flights where airline = 'VA' group by year, month, day, origin, dest, cabin"

    def get_delay(self):
        return 6

    def get_link_to_flight(self, flight: FlightData):
        return f'https://book.virginaustralia.com/dx/VADX/#/flight-selection?ADT=1&class=First&awardBooking=true&pos=us-en&channel=&activeMonth={flight.month:0>2}-{flight.day:0>2}-{flight.year}&journeyType=one-way&date={flight.month:0>2}-{flight.day:0>2}-{flight.year}&origin={flight.origin}&destination={flight.dest}'
        #return f'https://book.virginaustralia.com/dx/VADX/#/date-selection?journeyType=one-way&activeMonth={flight.month:0>2}-{flight.day:0>2}-{flight.year}&awardBooking=true&searchType=BRANDED&class=First&ADT=1&CHD=0&INF=0&origin={flight.origin}&destination={flight.dest}&direction=0&execution=undefined'

    async def get_results(self, flight: FlightData):
        #print(f'looking for {flight.month}/{flight.day}/{flight.year} from {flight.origin} to {flight.dest} in cabin {flight.cabin} using VIRGIN AUSTRALIA')

        ret = []
        required_verifies = 2
        verifies = required_verifies
        while verifies != 0:
            try:
                full_response = await self.get_flights(flight.year, flight.month, flight.day, flight.origin, flight.dest, flight.cabin)
                resp = json.loads(full_response.text)
                data = resp['data']['bookingAirSearch']['originalResponse']['unbundledOffers'][0]
                datastr = str(data)
                #only supports F flights

                if data and ('134000' in datastr or '95000' in datastr or '114000' in datastr):
                    ret.append(flight)

                verifies -= 1
            except Exception as e:
                raise FlightsError(e, full_response)

        return ret[:1] if len(ret) == required_verifies else []

    async def get_flights(self, year, month, day, origin, dest, cabin):

        cabins = {
            'F': 'First'
        }

        r_headers = {
            'content-type': 'application/json',
            'origin': 'https://book.virginaustralia.com',
            'referer': 'https://book.virginaustralia.com/dx/VADX/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'x-sabre-storefront': 'VADX',
        }

        r_json = {
            'operationName': 'bookingAirSearch',
            'variables': {
                'airSearchInput': {
                    'cabinClass': cabins[cabin],
                    'awardBooking': True,
                    'promoCodes': [
                        '',
                    ],
                    'searchType': 'BRANDED',
                    'itineraryParts': [
                        {
                            'from': {
                                'useNearbyLocations': False,
                                'code': origin,
                            },
                            'to': {
                                'useNearbyLocations': False,
                                'code': dest,
                            },
                            'when': {
                                'date': f'{year}-{month}-{day}',
                            },
                        },
                    ],
                    'passengers': {
                        'ADT': 1,
                    },
                },
            },
            'extensions': {},
            'query': 'query bookingAirSearch($airSearchInput: CustomAirSearchInput) {\n  bookingAirSearch(airSearchInput: $airSearchInput) {\n    originalResponse\n    __typename\n  }\n}\n',
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post('https://book.virginaustralia.com/api/graphql', headers=r_headers, json=r_json, timeout=None)
        except httpx.HTTPError as e:
            return str(e)
        except Exception as e:
            return "Unknown error"

        #print("elapsed time:", response.elapsed.total_seconds())
        if response.status_code != 200:
            print("=============== ERROR =============== ")
            print(response.text)
            print("===================================== ")
        return response
