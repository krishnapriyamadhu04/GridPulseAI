import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def get_weather(location: str):

    location = location.strip()

    if not location:
        raise ValueError("Please enter a location.")

    # -----------------------------------------
    # 1. FIND LOCATION
    # -----------------------------------------

    geo_response = requests.get(
        GEOCODING_URL,
        params={
            "name": location,
            "count": 10,
            "language": "en",
            "format": "json"
        },
        timeout=10
    )

    geo_response.raise_for_status()

    geo_data = geo_response.json()
    results = geo_data.get("results", [])

    if not results:
        raise ValueError(f"Location '{location}' was not found.")

    # Use the first relevant result
    place = results[0]

    latitude = place["latitude"]
    longitude = place["longitude"]

    # -----------------------------------------
    # 2. CURRENT WEATHER
    # -----------------------------------------

    weather_response = requests.get(
        WEATHER_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,"
                "relative_humidity_2m,"
                "apparent_temperature,"
                "weather_code,"
                "wind_speed_10m,"
                "wind_gusts_10m,"
                "is_day"
            ),
            "timezone": "auto"
        },
        timeout=10
    )

    weather_response.raise_for_status()

    weather_data = weather_response.json()
    current = weather_data["current"]

    # -----------------------------------------
    # 3. AIR QUALITY
    # -----------------------------------------

    air_response = requests.get(
        AIR_QUALITY_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "us_aqi,"
                "pm2_5,"
                "pm10,"
                "ozone"
            ),
            "timezone": "auto"
        },
        timeout=10
    )

    air_response.raise_for_status()

    air_data = air_response.json()
    air_current = air_data.get("current", {})

    return {
        # Location
        "location": place.get("name"),
        "country": place.get("country"),
        "country_code": place.get("country_code"),
        "admin1": place.get("admin1"),

        # Coordinates
        "latitude": latitude,
        "longitude": longitude,

        # Weather
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind_speed": current.get("wind_speed_10m"),
        "wind_gusts": current.get("wind_gusts_10m"),
        "weather_code": current.get("weather_code"),
        "is_day": current.get("is_day"),

        # Air quality
        "us_aqi": air_current.get("us_aqi"),
        "pm2_5": air_current.get("pm2_5"),
        "pm10": air_current.get("pm10"),
        "ozone": air_current.get("ozone"),

        # Time
        "time": current.get("time"),
        "timezone": weather_data.get("timezone")
    }