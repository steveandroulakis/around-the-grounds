"""Integration tests for scraping coordinator."""

import pytest
from unittest.mock import AsyncMock, patch
import aiohttp
from aioresponses import aioresponses
from datetime import datetime, timedelta

from around_the_grounds.scrapers.coordinator import ScraperCoordinator, ScrapingError
from around_the_grounds.models import Brewery, FoodTruckEvent


class TestScraperCoordinator:
    """Test the ScraperCoordinator class."""
    
    @pytest.fixture
    def coordinator(self):
        """Create a coordinator instance."""
        return ScraperCoordinator(max_concurrent=2, timeout=10, max_retries=2)
    
    @pytest.fixture
    def test_breweries(self):
        """Create test breweries."""
        return [
            Brewery(
                key="test-brewery-1",
                name="Test Brewery 1",
                url="https://example1.com/food-trucks",
                parser_config={}
            ),
            Brewery(
                key="test-brewery-2",
                name="Test Brewery 2", 
                url="https://example2.com/food-trucks",
                parser_config={}
            )
        ]
    
    @pytest.fixture
    def sample_events(self):
        """Create sample events for testing."""
        future_date = datetime.now() + timedelta(days=2)
        return [
            FoodTruckEvent(
                brewery_key="test-brewery-1",
                brewery_name="Test Brewery 1",
                food_truck_name="Test Truck 1",
                date=future_date,
                start_time=future_date.replace(hour=12),
                end_time=future_date.replace(hour=20)
            ),
            FoodTruckEvent(
                brewery_key="test-brewery-2",
                brewery_name="Test Brewery 2",
                food_truck_name="Test Truck 2",
                date=future_date,
                start_time=future_date.replace(hour=13),
                end_time=future_date.replace(hour=21)
            )
        ]
    
    @pytest.mark.asyncio
    async def test_scrape_all_success(self, coordinator, test_breweries, sample_events):
        """Test successful scraping of all breweries."""
        # Mock the parser registry and parsers
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Create mock parsers
            mock_parser_1 = AsyncMock()
            mock_parser_1.parse.return_value = [sample_events[0]]
            
            mock_parser_2 = AsyncMock()
            mock_parser_2.parse.return_value = [sample_events[1]]
            
            # Mock parser classes
            mock_parser_class_1 = AsyncMock(return_value=mock_parser_1)
            mock_parser_class_2 = AsyncMock(return_value=mock_parser_2)
            
            mock_registry.get_parser.side_effect = [mock_parser_class_1, mock_parser_class_2]
            
            events = await coordinator.scrape_all(test_breweries)
            
            assert len(events) == 2
            assert events[0].brewery_key == "test-brewery-1"
            assert events[1].brewery_key == "test-brewery-2"
            assert len(coordinator.get_errors()) == 0
    
    @pytest.mark.asyncio
    async def test_scrape_all_partial_failure(self, coordinator, test_breweries, sample_events):
        """Test scraping with partial failures."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # First parser succeeds
            mock_parser_1 = AsyncMock()
            mock_parser_1.parse.return_value = [sample_events[0]]
            mock_parser_class_1 = AsyncMock(return_value=mock_parser_1)
            
            # Second parser fails
            mock_parser_class_2 = AsyncMock()
            mock_parser_class_2.side_effect = aiohttp.ClientTimeout()
            
            mock_registry.get_parser.side_effect = [mock_parser_class_1, mock_parser_class_2]
            
            events = await coordinator.scrape_all(test_breweries)
            
            # Should have one successful event
            assert len(events) == 1
            assert events[0].brewery_key == "test-brewery-1"
            
            # Should have one error
            errors = coordinator.get_errors()
            assert len(errors) == 1
            assert errors[0].brewery.key == "test-brewery-2"
            assert errors[0].error_type == "Network Timeout"
    
    @pytest.mark.asyncio
    async def test_scrape_all_complete_failure(self, coordinator, test_breweries):
        """Test scraping with complete failures."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Both parsers fail
            mock_registry.get_parser.side_effect = [
                aiohttp.ClientTimeout(),
                ValueError("Parser error")
            ]
            
            events = await coordinator.scrape_all(test_breweries)
            
            # Should have no events
            assert len(events) == 0
            
            # Should have two errors
            errors = coordinator.get_errors()
            assert len(errors) == 2
    
    @pytest.mark.asyncio
    async def test_scrape_all_empty_brewery_list(self, coordinator):
        """Test scraping with empty brewery list."""
        events = await coordinator.scrape_all([])
        
        assert len(events) == 0
        assert len(coordinator.get_errors()) == 0
    
    @pytest.mark.asyncio
    async def test_retry_logic_success_after_failure(self, coordinator, test_breweries, sample_events):
        """Test retry logic that succeeds after initial failure."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Parser fails first time, succeeds second time
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = [
                aiohttp.ClientTimeout(),  # First attempt fails
                [sample_events[0]]        # Second attempt succeeds
            ]
            mock_parser_class = AsyncMock(return_value=mock_parser)
            
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_breweries[0]])
            
            # Should succeed on retry
            assert len(events) == 1
            assert len(coordinator.get_errors()) == 0
            
            # Parser should have been called twice (initial + 1 retry)
            assert mock_parser.parse.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_logic_max_retries_exceeded(self, coordinator, test_breweries):
        """Test retry logic when max retries are exceeded."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Parser always fails
            mock_parser = AsyncMock()
            mock_parser.parse.side_effect = aiohttp.ClientTimeout()
            mock_parser_class = AsyncMock(return_value=mock_parser)
            
            mock_registry.get_parser.return_value = mock_parser_class
            
            events = await coordinator.scrape_all([test_breweries[0]])
            
            # Should fail after all retries
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            
            # Parser should have been called max_retries times
            assert mock_parser.parse.call_count == coordinator.max_retries
    
    @pytest.mark.asyncio
    async def test_error_isolation(self, coordinator, test_breweries, sample_events):
        """Test that errors in one brewery don't affect others."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # First parser fails immediately
            mock_parser_1 = AsyncMock()
            mock_parser_1.parse.side_effect = ValueError("Parsing error")
            mock_parser_class_1 = AsyncMock(return_value=mock_parser_1)
            
            # Second parser succeeds
            mock_parser_2 = AsyncMock()
            mock_parser_2.parse.return_value = [sample_events[1]]
            mock_parser_class_2 = AsyncMock(return_value=mock_parser_2)
            
            mock_registry.get_parser.side_effect = [mock_parser_class_1, mock_parser_class_2]
            
            events = await coordinator.scrape_all(test_breweries)
            
            # Second brewery should still succeed
            assert len(events) == 1
            assert events[0].brewery_key == "test-brewery-2"
            
            # Should have one error for first brewery
            errors = coordinator.get_errors()
            assert len(errors) == 1
            assert errors[0].brewery.key == "test-brewery-1"
            assert errors[0].error_type == "Parser Error"
    
    @pytest.mark.asyncio
    async def test_filter_and_sort_events(self, coordinator, test_breweries):
        """Test event filtering and sorting."""
        now = datetime.now()
        past_event = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test",
            food_truck_name="Past Event",
            date=now - timedelta(days=1)  # Yesterday
        )
        future_event_1 = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test",
            food_truck_name="Future Event 1",
            date=now + timedelta(days=2),  # Day after tomorrow
            start_time=now + timedelta(days=2, hours=12)
        )
        future_event_2 = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test",
            food_truck_name="Future Event 2",
            date=now + timedelta(days=1),  # Tomorrow
            start_time=now + timedelta(days=1, hours=12)
        )
        far_future_event = FoodTruckEvent(
            brewery_key="test",
            brewery_name="Test",
            food_truck_name="Far Future Event",
            date=now + timedelta(days=10)  # Too far in future
        )
        
        events = [past_event, future_event_1, future_event_2, far_future_event]
        filtered_events = coordinator._filter_and_sort_events(events)
        
        # Should only include events within next 7 days, sorted by date
        assert len(filtered_events) == 2
        assert filtered_events[0].food_truck_name == "Future Event 2"  # Tomorrow (earlier)
        assert filtered_events[1].food_truck_name == "Future Event 1"  # Day after tomorrow
    
    @pytest.mark.asyncio
    async def test_network_error_handling(self, coordinator, test_breweries):
        """Test handling of various network errors."""
        error_test_cases = [
            (aiohttp.ClientTimeout(), "Network Timeout"),
            (aiohttp.ClientConnectorError(None, OSError("Connection failed")), "Network Error"),
            (aiohttp.ClientResponseError(None, None, status=404), "Network Error"),
        ]
        
        for exception, expected_error_type in error_test_cases:
            with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
                mock_parser = AsyncMock()
                mock_parser.parse.side_effect = exception
                mock_parser_class = AsyncMock(return_value=mock_parser)
                mock_registry.get_parser.return_value = mock_parser_class
                
                coordinator.errors = []  # Reset errors
                events = await coordinator.scrape_all([test_breweries[0]])
                
                assert len(events) == 0
                assert len(coordinator.get_errors()) == 1
                assert coordinator.get_errors()[0].error_type == expected_error_type
    
    @pytest.mark.asyncio
    async def test_configuration_error_no_retry(self, coordinator, test_breweries):
        """Test that configuration errors don't trigger retries."""
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Parser registry throws KeyError (parser not found)
            mock_registry.get_parser.side_effect = KeyError("Parser not found")
            
            events = await coordinator.scrape_all([test_breweries[0]])
            
            assert len(events) == 0
            assert len(coordinator.get_errors()) == 1
            assert coordinator.get_errors()[0].error_type == "Configuration Error"
            
            # Should only be called once (no retries for config errors)
            assert mock_registry.get_parser.call_count == 1
    
    def test_scraping_error_creation(self):
        """Test ScrapingError creation and properties."""
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
    
    def test_coordinator_initialization(self):
        """Test coordinator initialization with custom parameters."""
        coordinator = ScraperCoordinator(
            max_concurrent=10,
            timeout=60,
            max_retries=5
        )
        
        assert coordinator.max_concurrent == 10
        assert coordinator.timeout.total == 60
        assert coordinator.max_retries == 5
        assert coordinator.errors == []
    
    def test_has_errors(self, coordinator):
        """Test has_errors method."""
        # Initially no errors
        assert coordinator.has_errors() is False
        
        # Add an error
        brewery = Brewery("test", "Test", "https://example.com")
        error = ScrapingError(brewery, "Test", "Test message")
        coordinator.errors.append(error)
        
        assert coordinator.has_errors() is True
    
    @pytest.mark.asyncio
    async def test_concurrent_processing(self, test_breweries):
        """Test that breweries are processed concurrently."""
        coordinator = ScraperCoordinator(max_concurrent=2)
        
        with patch('around_the_grounds.scrapers.coordinator.ParserRegistry') as mock_registry:
            # Create slow parsers to test concurrency
            import asyncio
            
            async def slow_parse(session):
                await asyncio.sleep(0.1)  # Simulate slow parsing
                return []
            
            mock_parser_1 = AsyncMock()
            mock_parser_1.parse = slow_parse
            mock_parser_class_1 = AsyncMock(return_value=mock_parser_1)
            
            mock_parser_2 = AsyncMock()
            mock_parser_2.parse = slow_parse
            mock_parser_class_2 = AsyncMock(return_value=mock_parser_2)
            
            mock_registry.get_parser.side_effect = [mock_parser_class_1, mock_parser_class_2]
            
            start_time = datetime.now()
            events = await coordinator.scrape_all(test_breweries)
            end_time = datetime.now()
            
            # Should complete in less time than sequential processing
            # (2 * 0.1s = 0.2s sequential, should be closer to 0.1s concurrent)
            duration = (end_time - start_time).total_seconds()
            assert duration < 0.15  # Allow some overhead