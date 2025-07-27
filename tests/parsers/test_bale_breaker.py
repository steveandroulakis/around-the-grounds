"""Tests for Bale Breaker parser."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import aiohttp

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore
import pytest
from aioresponses import aioresponses

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.bale_breaker import BaleBreakerParser


class TestBaleBreakerParser:
    """Test the BaleBreakerParser class."""

    @pytest.fixture
    def brewery(self) -> Brewery:
        """Create a test brewery for Bale Breaker."""
        return Brewery(
            key="yonder-balebreaker",
            name="Yonder Cider & Bale Breaker - Ballard",
            url="https://www.bbycballard.com/food-trucks-1-1",
            parser_config={},
        )

    @pytest.fixture
    def parser(self, brewery: Brewery) -> BaleBreakerParser:
        """Create a parser instance."""
        return BaleBreakerParser(brewery)

    @pytest.fixture
    def sample_html_with_calendar(self) -> str:
        """Sample HTML with calendar block."""
        return """
        <html><body>
            <div class="sqs-block calendar-block sqs-block-calendar" 
                 data-block-json='{"hSize":null,"floatDir":null,"collectionId":"61328af17400707612fccbc6"}'>
                <div class="sqs-block-content">
                    <!-- The calendar block is initialized by javascript. -->
                </div>
            </div>
        </body></html>
        """

    @pytest.fixture
    def sample_api_response(self) -> List[Dict[str, Any]]:
        """Sample API response with food truck events."""
        return [
            {
                "id": "test1",
                "title": "Georgia's Greek",
                "startDate": 1720800000000,  # July 12, 2024 timestamp in ms
                "endDate": 1720814400000,
                "location": {"addressTitle": "Bale Breaker x Yonder Cider"},
            },
            {
                "id": "test2",
                "title": "Wood Shop BBQ",
                "startDate": 1720886400000,  # July 13, 2024 timestamp in ms
                "endDate": 1720900800000,
                "location": {"addressTitle": "Bale Breaker x Yonder Cider"},
            },
        ]

    @pytest.mark.asyncio
    async def test_parse_success_with_api_data(
        self,
        parser: BaleBreakerParser,
        sample_html_with_calendar: str,
        sample_api_response: List[Dict[str, Any]],
    ) -> None:
        """Test successful parsing with API data."""
        with aioresponses() as m:
            # Mock the main page request
            m.get(parser.brewery.url, status=200, body=sample_html_with_calendar)

            # Mock the API requests for different months
            base_api_url = "https://www.bbycballard.com/api/open/GetItemsByMonth"
            for month in ["July-2025", "August-2025", "September-2025"]:
                api_url = f"{base_api_url}?month={month}&collectionId=61328af17400707612fccbc6"
                response_data = sample_api_response if month == "July-2025" else []
                m.get(api_url, status=200, payload=response_data)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) == 2
                assert all(
                    event.brewery_key == "yonder-balebreaker" for event in events
                )
                assert events[0].food_truck_name == "Georgia's Greek"
                assert events[1].food_truck_name == "Wood Shop BBQ"

    @pytest.mark.asyncio
    async def test_parse_no_collection_id_fallback(
        self, parser: BaleBreakerParser
    ) -> None:
        """Test fallback when no collection ID is found."""
        html_without_calendar = "<html><body><p>No calendar here</p></body></html>"

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=html_without_calendar)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should return fallback event
                assert len(events) == 1
                assert "Check Instagram @BaleBreaker" in events[0].food_truck_name
                assert events[0].brewery_key == "yonder-balebreaker"

    @pytest.mark.asyncio
    async def test_parse_api_error_fallback(
        self, parser: BaleBreakerParser, sample_html_with_calendar: str
    ) -> None:
        """Test fallback when API requests fail."""
        with aioresponses() as m:
            # Mock successful main page request
            m.get(parser.brewery.url, status=200, body=sample_html_with_calendar)

            # Mock failing API requests
            base_api_url = "https://www.bbycballard.com/api/open/GetItemsByMonth"
            for month in ["July-2025", "August-2025", "September-2025"]:
                api_url = f"{base_api_url}?month={month}&collectionId=61328af17400707612fccbc6"
                m.get(api_url, status=500)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should return fallback event when API fails
                assert len(events) == 1
                assert "Check Instagram @BaleBreaker" in events[0].food_truck_name

    @pytest.mark.asyncio
    async def test_parse_network_error_fallback(
        self, parser: BaleBreakerParser
    ) -> None:
        """Test handling of network errors with fallback."""
        with aioresponses() as m:
            m.get(parser.brewery.url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should return fallback instead of raising
                assert len(events) == 1
                assert "Check Instagram @BaleBreaker" in events[0].food_truck_name

    def test_extract_collection_id_from_calendar_block(
        self, parser: BaleBreakerParser
    ) -> None:
        """Test extracting collection ID from calendar block."""
        from bs4 import BeautifulSoup

        html = """
        <div class="calendar-block" data-block-json='{"collectionId":"test123"}'>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")

        collection_id = parser._extract_collection_id(soup)
        assert collection_id == "test123"

    def test_extract_collection_id_from_script(self, parser: BaleBreakerParser) -> None:
        """Test extracting collection ID from script tag."""
        from bs4 import BeautifulSoup

        html = """
        <script>
        var data = {"collectionId":"script456"};
        </script>
        """
        soup = BeautifulSoup(html, "html.parser")

        collection_id = parser._extract_collection_id(soup)
        assert collection_id == "script456"

    def test_extract_collection_id_not_found(self, parser: BaleBreakerParser) -> None:
        """Test when collection ID is not found."""
        from bs4 import BeautifulSoup

        html = "<html><body><p>No collection ID here</p></body></html>"
        soup = BeautifulSoup(html, "html.parser")

        collection_id = parser._extract_collection_id(soup)
        assert collection_id is None

    def test_parse_api_event_valid(self, parser: BaleBreakerParser) -> None:
        """Test parsing a valid API event."""
        event_data = {
            "title": "Test Food Truck",
            "startDate": 1720800000000,  # Timestamp in milliseconds
            "endDate": 1720814400000,
        }

        event = parser._parse_api_event(event_data)

        assert event is not None
        assert event.food_truck_name == "Test Food Truck"
        assert event.brewery_key == "yonder-balebreaker"
        assert isinstance(event.date, datetime)
        assert isinstance(event.end_time, datetime)

    def test_parse_api_event_no_title(self, parser: BaleBreakerParser) -> None:
        """Test parsing API event with no title."""
        event_data = {"startDate": 1720800000000}

        event = parser._parse_api_event(event_data)
        assert event is None

    def test_parse_api_event_no_start_date(self, parser: BaleBreakerParser) -> None:
        """Test parsing API event with no start date."""
        event_data = {"title": "Test Food Truck"}

        event = parser._parse_api_event(event_data)
        assert event is None

    def test_create_fallback_event(self, parser: BaleBreakerParser) -> None:
        """Test creating fallback event."""
        events = parser._create_fallback_event()

        assert len(events) == 1
        event = events[0]
        assert "Check Instagram @BaleBreaker" in event.food_truck_name
        assert event.description is not None and "check Instagram" in event.description
        assert event.brewery_key == "yonder-balebreaker"

    @pytest.mark.asyncio
    async def test_fetch_calendar_events_success(
        self, parser: BaleBreakerParser, sample_api_response: List[Dict[str, Any]]
    ) -> None:
        """Test successful calendar events fetch."""
        collection_id = "test123"

        with aioresponses() as m:
            # Mock API requests for different months
            base_api_url = "https://www.bbycballard.com/api/open/GetItemsByMonth"
            for month in ["July-2025", "August-2025", "September-2025"]:
                api_url = f"{base_api_url}?month={month}&collectionId={collection_id}"
                response_data = sample_api_response if month == "July-2025" else []
                m.get(api_url, status=200, payload=response_data)

            async with aiohttp.ClientSession() as session:
                events = await parser._fetch_calendar_events(session, collection_id)

                assert len(events) == 2
                assert events[0].food_truck_name == "Georgia's Greek"
                assert events[1].food_truck_name == "Wood Shop BBQ"

    @pytest.mark.asyncio
    async def test_fetch_calendar_events_api_error(
        self, parser: BaleBreakerParser
    ) -> None:
        """Test calendar events fetch with API errors."""
        collection_id = "test123"

        with aioresponses() as m:
            # Mock failing API requests
            base_api_url = "https://www.bbycballard.com/api/open/GetItemsByMonth"
            for month in ["July-2025", "August-2025", "September-2025"]:
                api_url = f"{base_api_url}?month={month}&collectionId={collection_id}"
                m.get(api_url, status=500)

            async with aiohttp.ClientSession() as session:
                events = await parser._fetch_calendar_events(session, collection_id)

                # Should return empty list on API errors
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_real_html_fixture(
        self, parser: BaleBreakerParser, html_fixtures_dir: Path
    ) -> None:
        """Test parsing with real HTML fixture from the website."""
        fixture_path = html_fixtures_dir / "bale_breaker_sample.html"

        if fixture_path.exists():
            real_html = fixture_path.read_text()

            with aioresponses() as m:
                m.get(parser.brewery.url, status=200, body=real_html)

                # Mock API responses since we can't make real API calls in tests
                base_api_url = "https://www.bbycballard.com/api/open/GetItemsByMonth"
                for month in ["July-2025", "August-2025", "September-2025"]:
                    api_url = f"{base_api_url}?month={month}&collectionId=61328af17400707612fccbc6"
                    m.get(api_url, status=200, payload=[])

                async with aiohttp.ClientSession() as session:
                    # This should not raise an error regardless of content
                    events = await parser.parse(session)
                    assert isinstance(events, list)
                    # Should at least have fallback event if no API data
                    assert len(events) >= 1

    def test_timezone_conversion_pdt_summer(self, parser: BaleBreakerParser) -> None:
        """Test timezone conversion during PDT (Pacific Daylight Time) period."""
        # July 12, 2024 16:00 UTC (summer - PDT is UTC-7)
        utc_timestamp_ms = 1720800000000  # July 12, 2024 16:00:00 UTC

        event_data = {
            "title": "Test Summer Event",
            "startDate": utc_timestamp_ms,
            "endDate": utc_timestamp_ms + (4 * 60 * 60 * 1000),  # +4 hours
        }

        event = parser._parse_api_event(event_data)

        assert event is not None
        # In PDT (UTC-7), 16:00 UTC should be 09:00 PDT
        assert event.date.hour == 9
        assert event.end_time is not None
        assert event.end_time.hour == 13

        # Verify using proper timezone
        utc_time = datetime.fromtimestamp(utc_timestamp_ms / 1000, tz=timezone.utc)
        pacific_tz = ZoneInfo("America/Los_Angeles")
        expected_pacific = utc_time.astimezone(pacific_tz)

        # Event times should match proper timezone conversion
        assert event.date.hour == expected_pacific.hour
        assert event.date.minute == expected_pacific.minute

    def test_timezone_conversion_pst_winter(self, parser: BaleBreakerParser) -> None:
        """Test timezone conversion during PST (Pacific Standard Time) period."""
        # January 15, 2024 14:00 UTC (winter - PST is UTC-8)
        utc_timestamp_ms = 1705327200000  # January 15, 2024 14:00:00 UTC

        event_data = {
            "title": "Test Winter Event",
            "startDate": utc_timestamp_ms,
            "endDate": utc_timestamp_ms + (4 * 60 * 60 * 1000),  # +4 hours
        }

        event = parser._parse_api_event(event_data)

        assert event is not None
        # In PST (UTC-8), 14:00 UTC should be 06:00 PST
        assert event.date.hour == 6
        assert event.end_time is not None
        assert event.end_time.hour == 10

        # Verify using proper timezone
        utc_time = datetime.fromtimestamp(utc_timestamp_ms / 1000, tz=timezone.utc)
        pacific_tz = ZoneInfo("America/Los_Angeles")
        expected_pacific = utc_time.astimezone(pacific_tz)

        # Event times should match proper timezone conversion
        assert event.date.hour == expected_pacific.hour
        assert event.date.minute == expected_pacific.minute

    def test_timezone_handles_dst_transition(self, parser: BaleBreakerParser) -> None:
        """Test timezone conversion around DST transitions."""
        # Test a time during DST transition (Spring forward: March 10, 2024)
        # 10:00 UTC on March 10, 2024 (during transition)
        utc_timestamp_ms = 1710072000000  # March 10, 2024 10:00:00 UTC

        event_data = {
            "title": "DST Transition Test",
            "startDate": utc_timestamp_ms,
        }

        event = parser._parse_api_event(event_data)

        assert event is not None

        # Verify the timezone conversion matches system expectations
        utc_time = datetime.fromtimestamp(utc_timestamp_ms / 1000, tz=timezone.utc)
        pacific_tz = ZoneInfo("America/Los_Angeles")
        expected_pacific = utc_time.astimezone(pacific_tz)

        # Event should use the correct offset for that specific date
        assert event.date.hour == expected_pacific.hour
        assert event.date.day == expected_pacific.day
