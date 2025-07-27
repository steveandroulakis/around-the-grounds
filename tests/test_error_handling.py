"""Essential error handling tests."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from around_the_grounds.models import Brewery
from around_the_grounds.scrapers.coordinator import ScraperCoordinator, ScrapingError


class TestErrorHandling:
    """Essential error handling test suite."""

    @pytest.fixture
    def test_brewery(self) -> Brewery:
        """Create a test brewery."""
        return Brewery(
            key="test-brewery",
            name="Test Brewery",
            url="https://example.com/food-trucks",
        )

    @pytest.fixture
    def coordinator(self) -> ScraperCoordinator:
        """Create a coordinator for testing."""
        return ScraperCoordinator(max_concurrent=2, timeout=5, max_retries=2)

    @pytest.mark.asyncio
    async def test_connection_timeout_error(
        self, coordinator: ScraperCoordinator, test_brewery: Brewery
    ) -> None:
        """Test handling of connection timeouts."""
        with patch(
            "around_the_grounds.scrapers.coordinator.ParserRegistry.get_parser"
        ) as mock_get_parser:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = asyncio.TimeoutError()
            def mock_parser_class(brewery: Brewery) -> AsyncMock:
                return mock_parser
            mock_get_parser.return_value = mock_parser_class

            events = await coordinator.scrape_all([test_brewery])

            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert error.error_type == "Network Timeout"

    @pytest.mark.asyncio
    async def test_parser_not_found_error(
        self, coordinator: ScraperCoordinator, test_brewery: Brewery
    ) -> None:
        """Test handling when parser is not found."""
        with patch(
            "around_the_grounds.scrapers.coordinator.ParserRegistry.get_parser"
        ) as mock_get_parser:
            mock_get_parser.side_effect = ValueError("Parser not found")

            events = await coordinator.scrape_all([test_brewery])

            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert (
                error.error_type == "Unexpected Error"
            )  # This is what the coordinator actually returns

    def test_scraping_error_properties(self) -> None:
        """Test ScrapingError properties."""
        brewery = Brewery(key="test", name="Test Brewery", url="https://test.com")
        error = ScrapingError(
            brewery=brewery, error_type="Test Error", message="Test message"
        )

        assert error.brewery.name == "Test Brewery"
        assert error.error_type == "Test Error"
        assert error.message == "Test message"
        assert str(error) == "Test Error: Test message"
