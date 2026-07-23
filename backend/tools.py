"""
Tools the agent can call (OpenAI-style function calling).

Two example tools are implemented out of the box, using free, keyless APIs
so the project works with zero extra setup:

  * get_current_time  -> current date/time for a given IANA timezone
  * get_weather       -> current weather for a city (via Open-Meteo)

Add your own tools by:
  1. Writing a function below.
  2. Adding its JSON schema to TOOL_SCHEMAS.
  3. Registering it in TOOL_IMPLEMENTATIONS.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
import requests


# --------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------

def get_current_time(timezone: str = "UTC") -> str:
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        return f"Unknown timezone '{timezone}'. Try something like 'Asia/Karachi' or 'UTC'."
    now = datetime.now(tz)
    return now.strftime("%A, %d %B %Y, %I:%M %p (%Z)")


def get_weather(city: str) -> str:
    try:
        # 1. Geocode the city name to lat/lon (free, no API key required)
        geo_resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
            timeout=10,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
        results = geo_data.get("results")
        if not results:
            return f"Could not find a location named '{city}'."

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        label = f"{place.get('name')}, {place.get('country', '')}".strip(", ")

        # 2. Fetch current weather for those coordinates
        weather_resp = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
            timeout=10,
        )
        weather_resp.raise_for_status()
        current = weather_resp.json().get("current_weather", {})
        if not current:
            return f"Weather data is unavailable for {label} right now."

        temp = current.get("temperature")
        wind = current.get("windspeed")
        return f"Current weather in {label}: {temp}°C, wind speed {wind} km/h."
    except requests.RequestException as exc:
        return f"Weather lookup failed: {exc}"


# --------------------------------------------------------------------------
# JSON schemas exposed to the LLM (OpenAI / Groq function-calling format)
# --------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time for a given IANA timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "IANA timezone name, e.g. 'Asia/Karachi', 'America/New_York', 'UTC'.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a given city name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. 'Lahore', 'London', 'New York'.",
                    }
                },
                "required": ["city"],
            },
        },
    },
]

TOOL_IMPLEMENTATIONS = {
    "get_current_time": get_current_time,
    "get_weather": get_weather,
}


def execute_tool_call(name: str, arguments: dict) -> str:
    """Runs a tool by name and returns a string result (safe for any errors)."""
    fn = TOOL_IMPLEMENTATIONS.get(name)
    if fn is None:
        return f"Error: unknown tool '{name}'."
    try:
        return str(fn(**arguments))
    except Exception as exc:
        return f"Error running tool '{name}': {exc}"
