import requests
import json
from pprint import pprint
# request = requests.post('https://www.aa.com/booking/api/search/calendar', 
#                         headers = {'User-Agent' : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0', 
#                                    'Referer' : 'https://www.aa.com/booking/choose-flights/1', 
#                                    'Origin' : 'https://www.aa.com', 
#                                    'Content-Type' : 'application/json'}, 
#                         json = {"metadata":{"selectedProducts":[],"tripType":"OneWay","udo":{}},"passengers":[{"type":"adult","count":1}],"requestHeader":{"clientId":"AAcom"},"slices":[{"allCarriers":True,"cabin":"BUSINESS,FIRST","departureDate":"2024-12-01","destination":"ORD","destinationNearbyAirports":False,"maxStops":0,"origin":"TYO","originNearbyAirports":False}, {"allCarriers":True,"cabin":"BUSINESS,FIRST","departureDate":"2025-01-01","destination":"ORD","destinationNearbyAirports":False,"maxStops":0,"origin":"TYO","originNearbyAirports":False}],"tripOptions":{"corporateBooking":False,"fareType":"Lowest","locale":"en_US","pointOfSale":None,"searchType":"Award"},"loyaltyInfo":None,"version":"","queryParams":{"sliceIndex":0,"sessionId":"","solutionSet":"","solutionId":""}})

# data = json.loads(request.text)
with open('response.json', 'r') as f:
    data = json.load(f)

# pprint(data)
# with open('response.json', 'w') as f:
#     json.dump(data, f, indent=4)

weeks = data["calendarMonths"][0]["weeks"]
for w in weeks:
    week = w["days"]
    for day in week:
        if day["solution"] != None:
            print(day["date"])