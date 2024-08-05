from modules.flightmaster.flightdata import FlightData

class Airline:
    def __init__(self):
        pass

    def __str__(self):
        "Airline Parent"

    def is_valid_alert(self, origin: str, dest: str, cabin: str):
        return False

    def get_query(self):
        return None

    async def get_results(self, flight: FlightData):
        return None
