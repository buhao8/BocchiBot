class FlightUser():
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.email = data["email"]
        self.phone = data["phone"]

class FlightData():
    def __init__(self, data):
        self.uid = data["user_id"] if 'user_id' in data.keys() else -1
        self.year = data["year"]
        self.month = data["month"]
        self.day = data['day'] if 'day' in data.keys() else 0
        self.origin = data["origin"]
        self.dest = data["dest"]
        self.cabin = data["cabin"]
        self.stops = data["stops"] if "stops" in data.keys() else 0
        self.airline = data["airline"] if "airline" in data.keys() else "No Airline"

    def __str__(self):
        return f"""uid={self.uid}
year={self.year}
month={self.month}
day={self.day}
origin={self.origin}
dest={self.dest}
cabin={self.cabin}
airline={self.airline}"""

class FlightsError(Exception):
    def __init__(self, message, error):
        super().__init__(message)
        self.error = error

    def __str__(self):
        if hasattr(self.error, 'status_code'):
            return (f"\n\nstatus_code: {self.error.status_code}"
                  + f"\n\nresponse: {self.error.text}")
        return f"\n\nresponse: {self.error}"
