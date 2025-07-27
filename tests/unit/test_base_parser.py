"""Unit tests for base parser functionality."""

from typing import List

import aiohttp
import pytest
from aioresponses import aioresponses
from bs4 import BeautifulSoup

from around_the_grounds.models import Brewery, FoodTruckEvent
from around_the_grounds.parsers.base import BaseParser


class ConcreteParser(BaseParser):
    """Concrete implementation of BaseParser for testing."""

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        """Concrete implementation of parse method."""
        return []


class TestBaseParser:
    """Test the BaseParser class."""

    @pytest.fixture
    def parser(self, sample_brewery: Brewery) -> ConcreteParser:
        """Create a parser instance for testing."""
        return ConcreteParser(sample_brewery)

    def test_parser_initialization(self, sample_brewery: Brewery) -> None:
        """Test parser initialization."""
        parser = ConcreteParser(sample_brewery)

        assert parser.brewery == sample_brewery
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
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test validation of valid events."""
        result = parser.validate_event(sample_food_truck_event)
        assert result is True

    def test_validate_event_missing_brewery_key(
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test validation with missing brewery key."""
        sample_food_truck_event.brewery_key = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_brewery_name(
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test validation with missing brewery name."""
        sample_food_truck_event.brewery_name = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_food_truck_name(
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test validation with missing food truck name."""
        sample_food_truck_event.food_truck_name = ""
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_validate_event_missing_date(
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test validation with missing date."""
        sample_food_truck_event.date = None  # type: ignore
        result = parser.validate_event(sample_food_truck_event)
        assert result is False

    def test_filter_valid_events(
        self, parser: ConcreteParser, sample_food_truck_event: FoodTruckEvent
    ) -> None:
        """Test filtering of events."""
        # Create valid and invalid events
        valid_event = sample_food_truck_event

        invalid_event = FoodTruckEvent(
            brewery_key="",  # Missing brewery key
            brewery_name="Test Brewery",
            food_truck_name="Test Truck",
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
        invalid_event1 = FoodTruckEvent("", "Brewery", "Truck", None)  # type: ignore
        invalid_event2 = FoodTruckEvent("key", "", "Truck", None)  # type: ignore

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
