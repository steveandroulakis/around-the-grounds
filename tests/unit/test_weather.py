"""Unit tests for weather module."""

import re

import pytest
from datetime import datetime
from typing import Optional
from unittest.mock import AsyncMock, Mock, patch

from aioresponses import aioresponses

from around_the_grounds.utils.weather import (
    LOCATION_LAT,
    LOCATION_LON,
    OPEN_METEO_URL,
    WMO_CODES,
    _describe_wind,
    _get_time_window_and_date,
    _summarize_hours,
    fetch_weather,
)


class TestDescribeWind:
    """Test wind speed description."""

    def test_calm_winds(self) -> None:
        assert _describe_wind(0.0) == "calm winds"
        assert _describe_wind(4.9) == "calm winds"

    def test_light_breeze(self) -> None:
        assert _describe_wind(5.0) == "light breeze"
        assert _describe_wind(14.9) == "light breeze"

    def test_breezy(self) -> None:
        assert _describe_wind(15.0) == "breezy"
        assert _describe_wind(24.9) == "breezy"

    def test_windy(self) -> None:
        assert _describe_wind(25.0) == "windy"
        assert _describe_wind(39.9) == "windy"

    def test_very_windy(self) -> None:
        assert _describe_wind(40.0) == "very windy"
        assert _describe_wind(100.0) == "very windy"


class TestWMOCodes:
    """Test WMO weather code mapping."""

    def test_clear_codes(self) -> None:
        assert WMO_CODES[0] == "clear sky"
        assert WMO_CODES[1] == "mainly clear"
        assert WMO_CODES[2] == "partly cloudy"

    def test_overcast(self) -> None:
        assert WMO_CODES[3] == "overcast"

    def test_fog_codes(self) -> None:
        assert WMO_CODES[45] == "foggy"
        assert WMO_CODES[48] == "depositing rime fog"

    def test_rain_codes(self) -> None:
        assert WMO_CODES[61] == "slight rain"
        assert WMO_CODES[63] == "moderate rain"
        assert WMO_CODES[65] == "heavy rain"

    def test_snow_codes(self) -> None:
        assert WMO_CODES[71] == "slight snowfall"
        assert WMO_CODES[73] == "moderate snowfall"
        assert WMO_CODES[75] == "heavy snowfall"

    def test_thunderstorm_codes(self) -> None:
        assert WMO_CODES[95] == "thunderstorm"
        assert WMO_CODES[96] == "thunderstorm with slight hail"
        assert WMO_CODES[99] == "thunderstorm with heavy hail"

    def test_drizzle_codes(self) -> None:
        assert WMO_CODES[51] == "light drizzle"
        assert WMO_CODES[53] == "moderate drizzle"
        assert WMO_CODES[55] == "dense drizzle"


class TestGetTimeWindowAndDate:
    """Test time window and date determination."""

    def test_before_6pm_afternoon_today(self) -> None:
        """Before 6pm PT: afternoon forecast for today."""
        now = datetime(2026, 3, 28, 10, 0)  # 10am
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_at_noon(self) -> None:
        """Noon should still be afternoon forecast for today."""
        now = datetime(2026, 3, 28, 12, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_at_midnight(self) -> None:
        """Midnight (hour=0) should be afternoon forecast for today."""
        now = datetime(2026, 3, 29, 0, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-29"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_early_morning(self) -> None:
        """3am should be afternoon forecast for today."""
        now = datetime(2026, 3, 28, 3, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_at_5pm(self) -> None:
        """5pm (hour=17) is before 6pm, should be afternoon today."""
        now = datetime(2026, 3, 28, 17, 30)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_6pm_evening_today(self) -> None:
        """6pm-9pm PT: evening forecast for today."""
        now = datetime(2026, 3, 28, 18, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Evening"
        assert hours == [18, 19, 20, 21]

    def test_8pm_evening_today(self) -> None:
        """8pm should be evening forecast for today."""
        now = datetime(2026, 3, 28, 20, 30)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-28"
        assert time_of_day == "Evening"
        assert hours == [18, 19, 20, 21]

    def test_9pm_afternoon_tomorrow(self) -> None:
        """9pm-midnight PT: afternoon forecast for tomorrow."""
        now = datetime(2026, 3, 28, 21, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-29"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_11pm_afternoon_tomorrow(self) -> None:
        """11pm should be afternoon forecast for tomorrow."""
        now = datetime(2026, 3, 28, 23, 30)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-03-29"
        assert time_of_day == "Afternoon"
        assert hours == [14, 15, 16, 17]

    def test_date_rollover_end_of_month(self) -> None:
        """9pm on last day of month should target next month."""
        now = datetime(2026, 3, 31, 22, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2026-04-01"
        assert time_of_day == "Afternoon"

    def test_date_rollover_end_of_year(self) -> None:
        """11pm on Dec 31 should target Jan 1 next year."""
        now = datetime(2026, 12, 31, 23, 0)
        target_date, time_of_day, hours = _get_time_window_and_date(now)

        assert target_date == "2027-01-01"
        assert time_of_day == "Afternoon"


class TestSummarizeHours:
    """Test hourly data summarization."""

    def _make_hourly_data(
        self,
        target_date: str = "2026-03-28",
        hours: list = None,
        temps: list = None,
        codes: list = None,
        winds: list = None,
        humidities: list = None,
        precip_probs: list = None,
    ) -> dict:
        """Build sample hourly data for testing."""
        if hours is None:
            hours = list(range(24))
        if temps is None:
            temps = [50.0] * len(hours)
        if codes is None:
            codes = [0] * len(hours)
        if winds is None:
            winds = [10.0] * len(hours)
        if humidities is None:
            humidities = [65] * len(hours)
        if precip_probs is None:
            precip_probs = [0] * len(hours)

        time_list = [f"{target_date}T{h:02d}:00" for h in hours]
        return {
            "time": time_list,
            "temperature_2m": temps,
            "weather_code": codes,
            "wind_speed_10m": winds,
            "relative_humidity_2m": humidities,
            "precipitation_probability": precip_probs,
        }

    def test_summarize_afternoon_hours(self) -> None:
        """Test summarizing afternoon hours with consistent data."""
        hourly = self._make_hourly_data(
            target_date="2026-03-28",
            hours=list(range(24)),
            temps=[50.0 + i for i in range(24)],
            codes=[3] * 24,  # overcast
            winds=[10.0] * 24,
            humidities=[65] * 24,
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "overcast" in result
        assert "light breeze" in result
        assert "65% humidity" in result
        # Average temp of hours 14-17: (64+65+66+67)/4 = 65.5 -> 66
        assert "66\u00b0F" in result

    def test_summarize_with_varying_weather_codes(self) -> None:
        """Test that the worst (highest) weather code is used when precip probability is high."""
        hourly = self._make_hourly_data(
            hours=list(range(24)),
            codes=[0] * 14 + [2, 3, 61, 1] + [0] * 6,  # worst=61 at hour 16
            precip_probs=[0] * 14 + [80, 80, 80, 80] + [0] * 6,  # high probability
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "slight rain" in result  # WMO code 61

    def test_summarize_precip_code_downgraded_when_low_probability(self) -> None:
        """Test that precipitation codes are downgraded when probability is below threshold."""
        hourly = self._make_hourly_data(
            hours=list(range(24)),
            codes=[0] * 14 + [2, 3, 61, 1] + [0] * 6,  # worst=61 at hour 16
            precip_probs=[0] * 14 + [10, 10, 10, 10] + [0] * 6,  # low probability
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "slight rain" not in result
        assert "overcast" in result  # Falls back to WMO code 3

    def test_summarize_uses_modal_code_not_max(self) -> None:
        """Test that the most frequent code wins over the most severe."""
        # 3 hours of slight rain (61), 1 hour of slight snowfall (71)
        # Mode is 61 (rain), max would be 71 (snow)
        hourly = self._make_hourly_data(
            hours=list(range(24)),
            codes=[0] * 14 + [61, 61, 61, 71] + [0] * 6,
            precip_probs=[0] * 14 + [80, 80, 80, 80] + [0] * 6,
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "slight rain" in result  # modal code 61, not snowfall 71

    def test_summarize_modal_tie_breaks_by_severity(self) -> None:
        """Test that ties in frequency are broken by severity (highest code)."""
        # 2 hours overcast (3), 2 hours partly cloudy (2) — tie, 3 wins
        hourly = self._make_hourly_data(
            hours=list(range(24)),
            codes=[0] * 14 + [2, 2, 3, 3] + [0] * 6,
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "overcast" in result  # code 3 wins the tie

    def test_summarize_no_matching_hours(self) -> None:
        """Test when no hours match the target date."""
        hourly = self._make_hourly_data(target_date="2026-03-27")

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is None

    def test_summarize_no_matching_target_hours(self) -> None:
        """Test when hours exist but not the target hours."""
        hourly = self._make_hourly_data(
            hours=[0, 1, 2, 3],
            temps=[50.0] * 4,
            codes=[0] * 4,
            winds=[10.0] * 4,
            humidities=[65] * 4,
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is None

    def test_summarize_wind_calm(self) -> None:
        """Test summary with calm winds."""
        hourly = self._make_hourly_data(winds=[2.0] * 24)

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "calm winds" in result

    def test_summarize_wind_very_windy(self) -> None:
        """Test summary with very windy conditions."""
        hourly = self._make_hourly_data(winds=[50.0] * 24)

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "very windy" in result

    def test_summarize_unknown_wmo_code(self) -> None:
        """Test summary with unknown WMO code."""
        hourly = self._make_hourly_data(codes=[999] * 24)

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "unknown conditions" in result

    def test_summarize_partial_hours(self) -> None:
        """Test when only some of the target hours are available."""
        hourly = self._make_hourly_data(
            hours=[14, 15],  # Only 2 of 4 target hours
            temps=[60.0, 62.0],
            codes=[2, 3],
            winds=[12.0, 14.0],
            humidities=[70, 72],
        )

        result = _summarize_hours(hourly, "2026-03-28", [14, 15, 16, 17])

        assert result is not None
        assert "61\u00b0F" in result  # avg of 60 and 62
        assert "overcast" in result  # worst code is 3
        assert "71% humidity" in result  # avg of 70 and 72

    def test_summarize_two_dates(self) -> None:
        """Test with data spanning two dates; only target date is used."""
        time_list = [
            f"2026-03-28T{h:02d}:00" for h in range(24)
        ] + [
            f"2026-03-29T{h:02d}:00" for h in range(24)
        ]
        temps = [50.0] * 24 + [70.0] * 24
        codes = [0] * 24 + [65] * 24
        winds = [10.0] * 24 + [40.0] * 24
        humidities = [65] * 24 + [90] * 24
        precip_probs = [0] * 24 + [90] * 24  # high probability tomorrow

        hourly = {
            "time": time_list,
            "temperature_2m": temps,
            "weather_code": codes,
            "wind_speed_10m": winds,
            "relative_humidity_2m": humidities,
            "precipitation_probability": precip_probs,
        }

        # Ask for tomorrow's data
        result = _summarize_hours(hourly, "2026-03-29", [14, 15, 16, 17])

        assert result is not None
        assert "70\u00b0F" in result
        assert "heavy rain" in result  # WMO 65, high precip prob
        assert "very windy" in result
        assert "90% humidity" in result


class TestFetchWeather:
    """Test the async fetch_weather function."""

    def _build_api_response(self, target_date: str = "2026-03-28") -> dict:
        """Build a realistic Open-Meteo API response."""
        hours = list(range(24))
        time_list = [f"{target_date}T{h:02d}:00" for h in hours]

        # Add a second day
        next_date = "2026-03-29"
        time_list += [f"{next_date}T{h:02d}:00" for h in hours]

        n = len(time_list)
        return {
            "hourly": {
                "time": time_list,
                "temperature_2m": [53.0] * n,
                "weather_code": [3] * n,
                "wind_speed_10m": [8.0] * n,
                "relative_humidity_2m": [66] * n,
            }
        }

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_success_afternoon(
        self, mock_now: Mock
    ) -> None:
        """Test successful weather fetch for afternoon window."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), payload=self._build_api_response("2026-03-28"))

            result = await fetch_weather()

        assert result is not None
        weather_summary, time_of_day = result
        assert time_of_day == "Afternoon"
        assert "53\u00b0F" in weather_summary
        assert "overcast" in weather_summary
        assert "light breeze" in weather_summary
        assert "66% humidity" in weather_summary

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_success_evening(
        self, mock_now: Mock
    ) -> None:
        """Test successful weather fetch for evening window."""
        mock_now.return_value = datetime(2026, 3, 28, 19, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), payload=self._build_api_response("2026-03-28"))

            result = await fetch_weather()

        assert result is not None
        weather_summary, time_of_day = result
        assert time_of_day == "Evening"

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_success_late_night_tomorrow(
        self, mock_now: Mock
    ) -> None:
        """Test weather fetch at 10pm targets tomorrow."""
        mock_now.return_value = datetime(2026, 3, 28, 22, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), payload=self._build_api_response("2026-03-28"))

            result = await fetch_weather()

        assert result is not None
        weather_summary, time_of_day = result
        assert time_of_day == "Afternoon"

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_http_error(self, mock_now: Mock) -> None:
        """Test weather fetch with HTTP error response."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), status=500)

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_http_404(self, mock_now: Mock) -> None:
        """Test weather fetch with 404 response."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), status=404)

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_network_error(self, mock_now: Mock) -> None:
        """Test weather fetch with network error."""
        import aiohttp

        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(
                OPEN_METEO_URL,
                exception=aiohttp.ClientConnectionError("Connection refused"),
            )

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_timeout(self, mock_now: Mock) -> None:
        """Test weather fetch with timeout."""
        import asyncio

        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), exception=asyncio.TimeoutError())

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_malformed_json(self, mock_now: Mock) -> None:
        """Test weather fetch with response missing hourly data."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), payload={"latitude": 47.68})

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_empty_hourly_data(self, mock_now: Mock) -> None:
        """Test weather fetch with hourly data that has no matching hours."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        # Provide hourly data for a different date entirely
        payload = {
            "hourly": {
                "time": ["2026-03-27T14:00", "2026-03-27T15:00"],
                "temperature_2m": [50.0, 51.0],
                "weather_code": [0, 0],
                "wind_speed_10m": [5.0, 5.0],
                "relative_humidity_2m": [60, 60],
            }
        }

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), payload=payload)

            result = await fetch_weather()

        assert result is None

    @pytest.mark.asyncio
    @patch("around_the_grounds.utils.weather.now_in_pacific_naive")
    async def test_fetch_weather_unexpected_exception(self, mock_now: Mock) -> None:
        """Test weather fetch with unexpected exception."""
        mock_now.return_value = datetime(2026, 3, 28, 14, 0)

        with aioresponses() as m:
            m.get(re.compile(r"^https://api\.open-meteo\.com/v1/forecast"), exception=RuntimeError("Unexpected error"))

            result = await fetch_weather()

        assert result is None


class TestLocationConfig:
    """Test that weather location coordinates are configurable."""

    def test_default_location_is_ballard(self) -> None:
        """Default coordinates should be Ballard, Seattle."""
        assert LOCATION_LAT == 47.6762
        assert LOCATION_LON == -122.3851

    @patch.dict("os.environ", {"WEATHER_LOCATION_LAT": "40.7128", "WEATHER_LOCATION_LON": "-74.0060"})
    def test_location_configurable_via_env(self) -> None:
        """Coordinates should be overridable via environment variables."""
        import importlib
        import around_the_grounds.utils.weather as weather_mod

        importlib.reload(weather_mod)
        try:
            assert weather_mod.LOCATION_LAT == 40.7128
            assert weather_mod.LOCATION_LON == -74.0060
        finally:
            # Restore defaults
            importlib.reload(weather_mod)
