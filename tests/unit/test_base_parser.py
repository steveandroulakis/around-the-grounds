"""Unit tests for base parser functionality."""

from typing import List

import aiohttp
import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from around_the_grounds.models import Venue, Event
from around_the_grounds.parsers.base import BaseParser


class ConcreteParser(BaseParser):
    """Concrete implementation of BaseParser for testing."""

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        """Concrete implementation of parse method."""
        return []


class TestBaseParser:
    """Test the BaseParser class."""

    @pytest.fixture
    def parser(self, sample_brewery: Venue) -> ConcreteParser:
        """Create a parser instance for testing."""
        return ConcreteParser(sample_brewery)

    def test_parser_initialization(self, sample_brewery: Venue) -> None:
        """Test parser initialization."""
        parser = ConcreteParser(sample_brewery)

        assert parser.venue == sample_brewery
        assert hasattr(parser, "logger")

    @pytest.mark.asyncio
    async def test_fetch_page_success(self, parser: ConcreteParser) -> None:
        """Test successful page fetching."""
        test_html = "<html><body><h1>Test</h1></body></html>"

        with aioresponses() as m:
            m.get(
                "https://example.com/test",
                status=200,
                body=test_html,
                content_type="text/html",
            )

            async with aiohttp.ClientSession() as session:
                soup = await parser.fetch_page(session, "https://example.com/test")

                assert isinstance(soup, BeautifulSoup)
                h1_element = soup.find("h1")
                assert h1_element is not None
                assert h1_element.text == "Test"

    @pytest.mark.asyncio
    async def test_fetch_page_404_error(self, parser: ConcreteParser) -> None:
        """Test handling of 404 errors."""
        with aioresponses() as m:
            m.get("https://example.com/test", status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Page not found \\(404\\)"):
                    await parser.fetch_page(session, "https://example.com/test")

    @pytest.mark.asyncio
    async def test_fetch_page_403_error(self, parser: ConcreteParser) -> None:
        """Test handling of 403 errors."""
        with aioresponses() as m:
            m.get("https://example.com/test", status=403)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Access forbidden \\(403\\)"):
                    await parser.fetch_page(session, "https://example.com/test")

    @pytest.mark.asyncio
    async def test_fetch_page_500_error(self, parser: ConcreteParser) -> None:
        """Test handling of 500 errors."""
        with aioresponses() as m:
            m.get("https://example.com/test", status=500)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Server error \\(500\\)"):
                    await parser.fetch_page(session, "https://example.com/test")

    @pytest.mark.asyncio
    async def test_fetch_page_empty_response(self, parser: ConcreteParser) -> None:
        """Test handling of empty responses."""
        with aioresponses() as m:
            m.get("https://example.com/test", status=200, body="")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Empty response"):
                    await parser.fetch_page(session, "https://example.com/test")

    @pytest.mark.asyncio
    async def test_fetch_page_network_error(self, parser: ConcreteParser) -> None:
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(
                "https://example.com/test",
                exception=aiohttp.ClientError("Network error"),
            )

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Network error fetching"):
                    await parser.fetch_page(session, "https://example.com/test")

    def test_validate_event_valid(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation of valid events."""
        result = parser.validate_event(sample_food_truck_event)
        assert result is True

    def test_validate_event_missing_venue_key(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing venue key."""
        sample_food_truck_event.venue_key = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_venue_name(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing venue name."""
        sample_food_truck_event.venue_name = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_title(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing title."""
        sample_food_truck_event.title = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_date(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing date."""
        sample_food_truck_event.date = None  # type: ignore
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_filter_valid_events(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test filtering of events."""
        valid_event = sample_food_truck_event

        invalid_event = Event(
            venue_key="",  # Missing venue key
            venue_name="Test Venue",
            title="Test Show",
            date=valid_event.date,
        )

        events = [valid_event, invalid_event]
        filtered_events = parser.filter_valid_events(events)

        assert len(filtered_events) == 1
        assert filtered_events[0] == valid_event

    def test_filter_valid_events_empty_list(self, parser: ConcreteParser) -> None:
        """Test filtering empty list of events."""
        filtered_events = parser.filter_valid_events([])
        assert filtered_events == []

    def test_filter_valid_events_all_invalid(self, parser: ConcreteParser) -> None:
        """Test filtering when all events are invalid."""
        invalid_event1 = Event("", "Venue", "Show", None)  # type: ignore
        invalid_event2 = Event("key", "", "Show", None)  # type: ignore

        events = [invalid_event1, invalid_event2]
        filtered_events = parser.filter_valid_events(events)

        assert filtered_events == []

    @pytest.mark.asyncio
    async def test_fetch_page_non_html_response(self, parser: ConcreteParser) -> None:
        """Test handling of non-HTML responses."""
        json_response = '{"data": "test"}'

        with aioresponses() as m:
            m.get(
                "https://example.com/test",
                status=200,
                body=json_response,
                content_type="application/json",
            )

            async with aiohttp.ClientSession() as session:
                # Should still work but log a warning
                soup = await parser.fetch_page(session, "https://example.com/test")
                assert isinstance(soup, BeautifulSoup)

    @pytest.mark.asyncio
    async def test_fetch_page_malformed_html(self, parser: ConcreteParser) -> None:
        """Test handling of malformed HTML."""
        malformed_html = "<html><body><div>Unclosed div</body></html>"

        with aioresponses() as m:
            m.get(
                "https://example.com/test",
                status=200,
                body=malformed_html,
                content_type="text/html",
            )

            async with aiohttp.ClientSession() as session:
                # BeautifulSoup should handle malformed HTML gracefully
                soup = await parser.fetch_page(session, "https://example.com/test")
                assert isinstance(soup, BeautifulSoup)
                assert soup.find("div") is not None

    def test_validate_event_missing_venue_key(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing venue key."""
        sample_food_truck_event.venue_key = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_venue_name(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing venue name."""
        sample_food_truck_event.venue_name = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_title(
        self, parser: ConcreteParser, sample_food_truck_event: Event
    ) -> None:
        """Test validation with missing title."""
        sample_food_truck_event.title = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False
