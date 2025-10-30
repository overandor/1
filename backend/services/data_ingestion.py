import random

def fetch_weather_data(city: str):
    """Fetches weather data for a given city."""
    return {"city": city, "temperature": random.uniform(-10, 30)}
