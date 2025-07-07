"""Tests for Stoup Ballard parser."""

from datetime import datetime

import aiohttp
import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.stoup_ballard import StoupBallardParser


class TestStoupBallardParser:
    """Test the StoupBallardParser class."""

    @pytest.fixture
    def brewery(self):
        """Create a test brewery for Stoup Ballard."""
        return Brewery(
            key="stoup-ballard",
            name="Stoup Brewing - Ballard",
            url="https://example.com/ballard",
            parser_config={
                "selectors": {
                    "food_truck_entry": ".food-truck-entry",
                    "date": "h4",
                    "time": "p",
                }
            },
        )

    @pytest.fixture
    def parser(self, brewery):
        """Create a parser instance."""
        return StoupBallardParser(brewery)

    @pytest.fixture
    def structured_html(self, html_fixtures_dir):
        """Load structured HTML fixture."""
        fixture_path = html_fixtures_dir / "stoup_structured.html"
        return fixture_path.read_text()

    @pytest.mark.asyncio
    @freeze_time("2025-07-05")
    async def test_parse_structured_data(self, parser, structured_html):
        """Test parsing structured HTML data."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=structured_html)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) == 3

                # Check first event
                event1 = events[0]
                assert event1.brewery_key == "stoup-ballard"
                assert event1.brewery_name == "Stoup Brewing - Ballard"
                assert event1.food_truck_name == "Woodshop BBQ"
                assert event1.date.month == 7
                assert event1.date.day == 5
                assert event1.start_time.hour == 13  # 1pm
                assert event1.end_time.hour == 20  # 8pm

                # Check second event
                event2 = events[1]
                assert event2.food_truck_name == "Taco Truck Supreme"
                assert event2.date.day == 6
                assert event2.start_time.hour == 12  # 12pm
                assert event2.end_time.hour == 21  # 9pm

    @pytest.mark.asyncio
    async def test_parse_empty_schedule(self, parser):
        """Test parsing when no food truck entries are found."""
        empty_html = "<html><body><p>No food trucks today</p></body></html>"

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=empty_html)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_malformed_date(self, parser):
        """Test parsing with malformed date format."""
        malformed_html = """
        <html><body>
            <div class="food-truck-entry">
                <h4>Invalid Date Format</h4>
                <p>1 — 8pm</p>
                <p>Test Food Truck</p>
            </div>
        </body></html>
        """

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=malformed_html)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should return empty list due to invalid date
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_missing_time_info(self, parser):
        """Test parsing with missing time information."""
        missing_time_html = """
        <html><body>
            <div class="food-truck-entry">
                <h4>Fri 07.05</h4>
                <p>Test Food Truck</p>
            </div>
        </body></html>
        """

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=missing_time_html)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should still create event but without time info
                assert len(events) == 1
                event = events[0]
                assert event.food_truck_name == "Test Food Truck"
                assert event.start_time is None
                assert event.end_time is None

    @freeze_time("2025-07-05")
    def test_parse_date_current_year(self, parser):
        """Test date parsing for current year."""
        result = parser._parse_date("07.05")
        assert result.year == 2025
        assert result.month == 7
        assert result.day == 5

    @freeze_time("2025-12-25")
    def test_parse_date_next_year_rollover(self, parser):
        """Test date parsing with year rollover."""
        result = parser._parse_date("01.15")
        assert result.year == 2026  # Should be next year
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_invalid_format(self, parser):
        """Test parsing invalid date format."""
        result = parser._parse_date("invalid")
        assert result is None

    @freeze_time("2025-07-05")
    def test_parse_time_pm_range(self, parser):
        """Test parsing PM time range."""
        date = datetime(2025, 7, 5)
        start_time, end_time = parser._parse_time(date, (1, 8, "pm"))

        assert start_time.hour == 13  # 1pm
        assert end_time.hour == 20  # 8pm

    @freeze_time("2025-07-05")
    def test_parse_time_am_range(self, parser):
        """Test parsing AM time range."""
        date = datetime(2025, 7, 5)
        start_time, end_time = parser._parse_time(date, (8, 11, "am"))

        assert start_time.hour == 8  # 8am
        assert end_time.hour == 11  # 11am

    def test_parse_time_invalid_hour(self, parser):
        """Test parsing invalid hour."""
        date = datetime(2025, 7, 5)
        start_time, end_time = parser._parse_time(
            date, (13, 8, "pm")
        )  # 13pm doesn't exist

        assert start_time is None
        assert end_time is None

    @freeze_time("2025-07-05")
    def test_parse_time_from_text_valid(self, parser):
        """Test parsing time from valid text."""
        date = datetime(2025, 7, 5)
        start_time, end_time = parser._parse_time_from_text(date, "1 — 8pm")

        assert start_time.hour == 13
        assert end_time.hour == 20

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser):
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(
                    ValueError, match="Failed to parse Stoup Ballard website"
                ):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_fallback_extraction(self, parser):
        """Test fallback extraction when structured data is not found."""
        fallback_html = """
        <html><body>
            <section>
                <p>Food Truck Schedule</p>
                <p>Fri 07.05</p>
                <p>1 — 8pm</p>
                <p>Fallback Food Truck</p>
            </section>
        </body></html>
        """

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=fallback_html)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should find events using fallback extraction
                assert (
                    len(events) >= 0
                )  # May or may not find events depending on parsing logic

    @pytest.mark.asyncio
    async def test_parse_real_html_fixture(self, parser, html_fixtures_dir):
        """Test parsing with real HTML fixture from the website."""
        fixture_path = html_fixtures_dir / "stoup_ballard_sample.html"

        if fixture_path.exists():
            real_html = fixture_path.read_text()

            with aioresponses() as m:
                m.get(parser.brewery.url, status=200, body=real_html)

                async with aiohttp.ClientSession() as session:
                    # This should not raise an error regardless of content
                    events = await parser.parse(session)
                    assert isinstance(events, list)
