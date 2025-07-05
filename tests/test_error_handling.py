"""Comprehensive error handling tests."""

import pytest
from unittest.mock import AsyncMock, patch, Mock
import aiohttp
from aioresponses import aioresponses
import asyncio
from datetime import datetime

from around_the_grounds.scrapers.coordinator import ScraperCoordinator, ScrapingError
from around_the_grounds.parsers.base import BaseParser
from around_the_grounds.parsers.stoup_ballard import StoupBallardParser
from around_the_grounds.parsers.bale_breaker import BaleBreakerParser
from around_the_grounds.models import Brewery, FoodTruckEvent


class TestErrorHandling:
    """Comprehensive error handling test suite."""
    
    @pytest.fixture
    def test_brewery(self):
        """Create a test brewery."""
        return Brewery(
            key="test-brewery",
            name="Test Brewery",
            url="https://example.com/food-trucks"
        )
    
    @pytest.fixture
    def coordinator(self):
        """Create a coordinator for testing."""
        return ScraperCoordinator(max_concurrent=2, timeout=5, max_retries=2)
    
    # Network Error Tests
    
    @pytest.mark.asyncio
    async def test_connection_timeout_error(self, coordinator, test_brewery):
        """Test handling of connection timeouts."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = aiohttp.ClientTimeout()
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert error.error_type == "Network Timeout"
            assert "timeout" in error.message.lower()
    
    @pytest.mark.asyncio
    async def test_dns_resolution_failure(self, coordinator, test_brewery):
        """Test handling of DNS resolution failures."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = aiohttp.ClientConnectorError(
                None, OSError("Name or service not known")
            )
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert error.error_type == "Network Error"
    
    @pytest.mark.asyncio
    async def test_ssl_certificate_error(self, coordinator, test_brewery):
        """Test handling of SSL certificate errors."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = aiohttp.ClientSSLError(
                None, "SSL certificate verification failed"
            )
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert error.error_type == "Network Error"
    
    @pytest.mark.asyncio
    async def test_http_status_errors(self, test_brewery):
        """Test handling of various HTTP status errors."""
        parser = StoupBallardParser(test_brewery)
        
        status_codes = [404, 403, 500, 502, 503]
        
        for status_code in status_codes:
            with aioresponses() as m:
                m.get(test_brewery.url, status=status_code)
                
                async with aiohttp.ClientSession() as session:
                    with pytest.raises(ValueError) as exc_info:
                        await parser.fetch_page(session, test_brewery.url)
                    
                    error_message = str(exc_info.value)
                    assert str(status_code) in error_message
    
    # Parser Error Tests
    
    @pytest.mark.asyncio
    async def test_malformed_html_handling(self, test_brewery):
        """Test handling of malformed HTML."""
        parser = StoupBallardParser(test_brewery)
        malformed_html = "<html><body><div>Unclosed div<p>Unclosed paragraph</body>"
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body=malformed_html)
            
            async with aiohttp.ClientSession() as session:
                # Should not raise an error - BeautifulSoup handles malformed HTML
                soup = await parser.fetch_page(session, test_brewery.url)
                assert soup is not None
    
    @pytest.mark.asyncio
    async def test_empty_html_response(self, test_brewery):
        """Test handling of empty HTML responses."""
        parser = StoupBallardParser(test_brewery)
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body="")
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Empty response"):
                    await parser.fetch_page(session, test_brewery.url)
    
    @pytest.mark.asyncio
    async def test_non_html_response(self, test_brewery):
        """Test handling of non-HTML responses."""
        parser = StoupBallardParser(test_brewery)
        json_response = '{"error": "Not HTML content"}'
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body=json_response, content_type="application/json")
            
            async with aiohttp.ClientSession() as session:
                # Should still work but may log warnings
                soup = await parser.fetch_page(session, test_brewery.url)
                assert soup is not None
    
    @pytest.mark.asyncio
    async def test_missing_expected_elements(self, test_brewery):
        """Test handling when expected HTML elements are missing."""
        parser = StoupBallardParser(test_brewery)
        html_without_events = "<html><body><h1>No food trucks today</h1></body></html>"
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body=html_without_events)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                # Should return empty list, not raise error
                assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_invalid_date_formats(self, test_brewery):
        """Test handling of invalid date formats in HTML."""
        parser = StoupBallardParser(test_brewery)
        html_invalid_dates = """
        <html><body>
            <div class="food-truck-entry">
                <h4>Invalid Date</h4>
                <p>1 — 8pm</p>
                <p>Test Truck</p>
            </div>
            <div class="food-truck-entry">
                <h4>99.99</h4>
                <p>2 — 9pm</p>
                <p>Another Truck</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body=html_invalid_dates)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                # Should filter out events with invalid dates
                assert len(events) == 0
    
    # Configuration Error Tests
    
    @pytest.mark.asyncio
    async def test_parser_not_found_error(self, coordinator, test_brewery):
        """Test handling when parser is not found for brewery key."""
        # Use a brewery key that doesn't have a registered parser
        invalid_brewery = Brewery("invalid-key", "Invalid Brewery", "https://example.com")
        
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_registry.get_parser.side_effect = KeyError("Parser not found")
            
            events = await coordinator.scrape_all([invalid_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            error = coordinator.get_errors()[0]
            assert error.error_type == "Configuration Error"
            assert "Parser not found" in error.message
    
    @pytest.mark.asyncio
    async def test_invalid_brewery_url(self, coordinator):
        """Test handling of invalid brewery URLs."""
        invalid_brewery = Brewery("test", "Test", "not-a-valid-url")
        
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = aiohttp.InvalidURL("Invalid URL")
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([invalid_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
    
    # Data Validation Error Tests
    
    def test_event_validation_missing_brewery_key(self, test_brewery):
        """Test event validation with missing brewery key."""
        parser = StoupBallardParser(test_brewery)
        
        invalid_event = FoodTruckEvent(
            brewery_key="",  # Empty brewery key
            brewery_name="Test Brewery",
            food_truck_name="Test Truck",
            date=datetime.now()
        )
        
        assert parser.validate_event(invalid_event) is False
    
    def test_event_validation_missing_food_truck_name(self, test_brewery):
        """Test event validation with missing food truck name."""
        parser = StoupBallardParser(test_brewery)
        
        invalid_event = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test Brewery",
            food_truck_name="",  # Empty truck name
            date=datetime.now()
        )
        
        assert parser.validate_event(invalid_event) is False
    
    def test_event_validation_missing_date(self, test_brewery):
        """Test event validation with missing date."""
        parser = StoupBallardParser(test_brewery)
        
        invalid_event = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test Brewery", 
            food_truck_name="Test Truck",
            date=None  # Missing date
        )
        
        assert parser.validate_event(invalid_event) is False
    
    # Retry Logic Tests
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, coordinator, test_brewery):
        """Test that retry logic uses exponential backoff."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            with patch('asyncio.sleep') as mock_sleep:
                mock_parser = AsyncMock()
                mock_parser.parse.side_effect = [
                    aiohttp.ClientTimeout(),  # First attempt fails
                    aiohttp.ClientTimeout(),  # Second attempt fails
                    []  # Third attempt succeeds
                ]
                mock_parser_class = AsyncMock(return_value=mock_parser)
                mock_registry.get_parser.return_value = mock_parser_class
                
                events = await coordinator.scrape_all([test_brewery])
                
                # Should have called sleep with exponential backoff
                assert mock_sleep.call_count == 2
                sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
                assert sleep_calls[0] == 1  # 2^0
                assert sleep_calls[1] == 2  # 2^1
    
    @pytest.mark.asyncio
    async def test_no_retry_for_configuration_errors(self, coordinator, test_brewery):
        """Test that configuration errors don't trigger retries."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_registry.get_parser.side_effect = KeyError("Parser not found")
            
            events = await coordinator.scrape_all([test_brewery])
            
            # Should only be called once (no retries for config errors)
            assert mock_registry.get_parser.call_count == 1
            assert len(coordinator.get_errors()) == 1
            assert coordinator.get_errors()[0].error_type == "Configuration Error"
    
    @pytest.mark.asyncio
    async def test_no_retry_for_parser_errors(self, coordinator, test_brewery):
        """Test that parser errors don't trigger retries."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = ValueError("Parsing failed")
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_brewery])
            
            # Parser should only be called once (no retries for parser errors)
            assert mock_parser.parse.call_count == 1
            assert len(coordinator.get_errors()) == 1
            assert coordinator.get_errors()[0].error_type == "Parser Error"
    
    # Error Isolation Tests
    
    @pytest.mark.asyncio
    async def test_error_isolation_between_breweries(self, coordinator):
        """Test that errors in one brewery don't affect others."""
        breweries = [
            Brewery("failing", "Failing Brewery", "https://fail.com"),
            Brewery("working", "Working Brewery", "https://work.com")
        ]
        
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # First parser always fails
            mock_failing_parser = AsyncMock()
            mock_failing_parser.parse.side_effect = Exception("Always fails")
            mock_failing_parser_class = AsyncMock(return_value=mock_failing_parser)
            
            # Second parser always succeeds
            mock_working_parser = AsyncMock()
            mock_working_parser.parse.return_value = [
                FoodTruckEvent("working", "Working", "Truck", datetime.now())
            ]
            mock_working_parser_class = AsyncMock(return_value=mock_working_parser)
            
            mock_registry.get_parser.side_effect = [
                mock_failing_parser_class,
                mock_working_parser_class
            ]
            
            events = await coordinator.scrape_all(breweries)
            
            # Should have one successful event despite one brewery failing
            assert len(events) == 1
            assert events[0].brewery_key == "working"
            
            # Should have one error
            assert len(coordinator.get_errors()) == 1
            assert coordinator.get_errors()[0].brewery.key == "failing"
    
    # Resource Management Tests
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_error(self, coordinator, test_brewery):
        """Test that resources are properly cleaned up when errors occur."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = Exception("Test error")
            mock_parser_class = AsyncMock(return_value=mock_parser)
            mock_registry.get_parser.return_value = mock_parser_class
            
            # Should not raise unhandled exceptions
            events = await coordinator.scrape_all([test_brewery])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_error_handling(self, coordinator):
        """Test error handling with concurrent processing."""
        breweries = [
            Brewery(f"brewery-{i}", f"Brewery {i}", f"https://example{i}.com")
            for i in range(5)
        ]
        
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # All parsers fail with different errors
            def create_failing_parser(error_msg):
                mock_parser = AsyncMock()
                mock_parser.parse.side_effect = Exception(error_msg)
                return AsyncMock(return_value=mock_parser)
            
            mock_registry.get_parser.side_effect = [
                create_failing_parser(f"Error {i}") for i in range(5)
            ]
            
            events = await coordinator.scrape_all(breweries)
            
            # All should fail
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 5
            
            # Each error should be properly captured
            for i, error in enumerate(coordinator.get_errors()):
                assert error.brewery.key == f"brewery-{i}"
    
    # Edge Case Tests
    
    @pytest.mark.asyncio
    async def test_empty_response_body(self, test_brewery):
        """Test handling of responses with empty body."""
        parser = StoupBallardParser(test_brewery)
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body="")
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Empty response"):
                    await parser.fetch_page(session, test_brewery.url)
    
    @pytest.mark.asyncio
    async def test_very_large_response(self, test_brewery):
        """Test handling of very large responses."""
        parser = StoupBallardParser(test_brewery)
        large_html = "<html><body>" + "A" * 10000 + "</body></html>"
        
        with aioresponses() as m:
            m.get(test_brewery.url, status=200, body=large_html)
            
            async with aiohttp.ClientSession() as session:
                # Should handle large responses without error
                soup = await parser.fetch_page(session, test_brewery.url)
                assert soup is not None
    
    def test_scraping_error_properties(self):
        """Test ScrapingError object properties and behavior."""
        brewery = Brewery("test", "Test Brewery", "https://example.com")
        error = ScrapingError(
            brewery=brewery,
            error_type="Test Error",
            message="Test message",
            details="Test details"
        )
        
        assert error.brewery == brewery
        assert error.error_type == "Test Error"
        assert error.message == "Test message"
        assert error.details == "Test details"
        assert isinstance(error.timestamp, datetime)
        
        # Test string representation
        error_str = str(error)
        assert "Test Error" in error_str or "Test message" in error_str