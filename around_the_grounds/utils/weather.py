"""Fetch weather forecasts from Open-Meteo."""

import logging
import os
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

import aiohttp

from .timezone_utils import now_in_pacific_naive

logger = logging.getLogger(__name__)

# Default coordinates (Ballard, Seattle)
_DEFAULT_LAT = 47.6762
_DEFAULT_LON = -122.3851

LOCATION_LAT = float(os.getenv("WEATHER_LOCATION_LAT", str(_DEFAULT_LAT)))
LOCATION_LON = float(os.getenv("WEATHER_LOCATION_LON", str(_DEFAULT_LON)))

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code descriptions
WMO_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}


def _describe_wind(speed_kmh: float) -> str:
    """Convert wind speed to a human-readable description."""
    if speed_kmh < 5:
        return "calm winds"
    elif speed_kmh < 15:
        return "light breeze"
    elif speed_kmh < 25:
        return "breezy"
    elif speed_kmh < 40:
        return "windy"
    else:
        return "very windy"


def _get_time_window_and_date(
    now: datetime,
) -> tuple[str, str, list[int]]:
    """Determine the forecast time window, time-of-day label, and target date.

    Returns:
        (target_date as "YYYY-MM-DD", time_of_day label, list of hours to average)
    """
    hour = now.hour
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

    if hour < 18:
        # Before 6pm: afternoon forecast for today
        return today_str, "Afternoon", [14, 15, 16, 17]
    elif hour < 21:
        # 6pm-9pm: early evening forecast for today
        return today_str, "Evening", [18, 19, 20, 21]
    else:
        # 9pm-midnight: afternoon forecast for tomorrow
        return tomorrow_str, "Afternoon", [14, 15, 16, 17]


# Precipitation-related WMO codes (drizzle, rain, snow, showers, thunderstorms)
_PRECIP_CODES = {
    51, 53, 55, 56, 57,  # drizzle
    61, 63, 65, 66, 67,  # rain
    71, 73, 75, 77,      # snow
    80, 81, 82, 85, 86,  # showers
    95, 96, 99,          # thunderstorms
}

# Minimum average precipitation probability to report precipitation weather codes
_PRECIP_PROBABILITY_THRESHOLD = 40


def _summarize_hours(
    hourly_data: dict,
    target_date: str,
    hours: list[int],
) -> Optional[str]:
    """Average hourly data for the given hours and return a weather summary string."""
    temps = []
    codes = []
    winds = []
    humidities = []
    precip_probs = []

    has_precip_prob = "precipitation_probability" in hourly_data

    for i, t in enumerate(hourly_data["time"]):
        date_part, time_part = t.split("T")
        hr = int(time_part.split(":")[0])
        if date_part == target_date and hr in hours:
            temps.append(hourly_data["temperature_2m"][i])
            codes.append(hourly_data["weather_code"][i])
            winds.append(hourly_data["wind_speed_10m"][i])
            humidities.append(hourly_data["relative_humidity_2m"][i])
            if has_precip_prob:
                precip_probs.append(hourly_data["precipitation_probability"][i])

    if not temps:
        return None

    avg_temp = round(sum(temps) / len(temps))
    avg_wind = sum(winds) / len(winds)
    avg_humidity = round(sum(humidities) / len(humidities))
    avg_precip_prob = (
        sum(precip_probs) / len(precip_probs) if precip_probs else 0
    )

    # Pick the most representative weather code for the window:
    # 1. If avg precipitation probability is below threshold, filter out
    #    precipitation codes (drizzle, rain, snow, etc.) to avoid
    #    overreporting unlikely conditions.
    # 2. Use the most frequent (modal) code — this reflects what you'd
    #    actually experience across the window, rather than amplifying a
    #    single extreme hour.
    # 3. Break ties by severity (highest code wins).
    effective_codes = codes
    if avg_precip_prob < _PRECIP_PROBABILITY_THRESHOLD:
        non_precip = [c for c in codes if c not in _PRECIP_CODES]
        if non_precip:
            effective_codes = non_precip
        else:
            effective_codes = [3]  # default to overcast

    # Most frequent code, ties broken by highest value (most severe)
    code_counts = Counter(effective_codes)
    max_count = max(code_counts.values())
    most_common = [code for code, count in code_counts.items() if count == max_count]
    representative_code = max(most_common)

    condition = WMO_CODES.get(representative_code, "unknown conditions")
    wind_desc = _describe_wind(avg_wind)

    # Include precipitation probability for precipitation conditions
    if representative_code in _PRECIP_CODES and avg_precip_prob > 0:
        prob_pct = round(avg_precip_prob)
        return (
            f"{avg_temp}\u00b0F, chance of {condition} ({prob_pct}%), "
            f"{wind_desc}, {avg_humidity}% humidity"
        )

    return f"{avg_temp}\u00b0F, {condition}, {wind_desc}, {avg_humidity}% humidity"


async def fetch_weather() -> Optional[tuple[str, str]]:
    """Fetch weather forecast for the configured location.

    Location is controlled by WEATHER_LOCATION_LAT and WEATHER_LOCATION_LON
    environment variables (defaults to Ballard, Seattle).

    Returns:
        Tuple of (weather_summary, time_of_day) or None if the fetch fails.
        weather_summary example: "53\u00b0F, overcast, calm winds, 66% humidity"
        time_of_day example: "Afternoon" or "Evening"
    """
    now = now_in_pacific_naive()
    target_date, time_of_day, target_hours = _get_time_window_and_date(now)

    params = {
        "latitude": LOCATION_LAT,
        "longitude": LOCATION_LON,
        "hourly": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m,precipitation_probability",
        "temperature_unit": "fahrenheit",
        "timezone": "America/Los_Angeles",
        "forecast_days": 2,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                OPEN_METEO_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.error(
                        "Open-Meteo API returned status %d", response.status
                    )
                    return None

                data = await response.json()
                hourly = data.get("hourly")
                if not hourly:
                    logger.error("Open-Meteo response missing hourly data")
                    return None

                summary = _summarize_hours(hourly, target_date, target_hours)
                if not summary:
                    logger.error(
                        "Could not summarize weather for %s hours %s",
                        target_date,
                        target_hours,
                    )
                    return None

                logger.info("Weather for %s (%s): %s", target_date, time_of_day, summary)
                return summary, time_of_day

    except aiohttp.ClientError as e:
        logger.error("Failed to fetch weather from Open-Meteo: %s", e)
        return None
    except Exception as e:
        logger.error("Unexpected error fetching weather: %s", e)
        return None
