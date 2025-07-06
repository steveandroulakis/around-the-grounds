"""Integration tests for CLI functionality."""

import pytest
from unittest.mock import patch, AsyncMock, Mock
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from around_the_grounds.main import main, load_brewery_config, format_events_output, scrape_food_trucks
from around_the_grounds.models import Brewery, FoodTruckEvent
from around_the_grounds.scrapers.coordinator import ScrapingError


class TestCLI:
    """Test CLI functionality."""
    
    @pytest.fixture
    def temp_config_file(self, test_breweries_config):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_breweries_config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink()
    
    @pytest.fixture
    def sample_cli_events(self):
        """Create sample events for CLI testing."""
        future_date = datetime.now() + timedelta(days=1)
        return [
            FoodTruckEvent(
                brewery_key="test-brewery",
                brewery_name="Test Brewery",
                food_truck_name="Amazing BBQ Truck",
                date=future_date,
                start_time=future_date.replace(hour=12),
                end_time=future_date.replace(hour=20),
                description="Delicious BBQ all day"
            ),
            FoodTruckEvent(
                brewery_key="test-brewery-2",
                brewery_name="Test Brewery 2",
                food_truck_name="Taco Supreme",
                date=future_date,
                start_time=future_date.replace(hour=11),
                end_time=future_date.replace(hour=21)
            )
        ]
    
    def test_load_brewery_config_success(self, temp_config_file):
        """Test successful loading of brewery configuration."""
        breweries = load_brewery_config(temp_config_file)
        
        assert len(breweries) == 2
        assert breweries[0].key == "test-brewery-1"
        assert breweries[0].name == "Test Brewery 1"
        assert breweries[0].url == "https://example1.com/food-trucks"
        assert breweries[1].key == "test-brewery-2"
    
    def test_load_brewery_config_default_path(self):
        """Test loading brewery config from default path."""
        # Should use the default config file
        with patch('around_the_grounds.main.Path') as mock_path:
            mock_config_path = mock_path.return_value.parent / "config" / "breweries.json"
            mock_config_path.exists.return_value = True
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = json.dumps({
                    "breweries": [{"key": "default", "name": "Default", "url": "https://example.com"}]
                })
                
                with patch('json.load') as mock_json_load:
                    mock_json_load.return_value = {
                        "breweries": [{"key": "default", "name": "Default", "url": "https://example.com"}]
                    }
                    
                    breweries = load_brewery_config()
                    assert len(breweries) == 1
                    assert breweries[0].key == "default"
    
    def test_load_brewery_config_file_not_found(self):
        """Test loading config when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_brewery_config("/nonexistent/config.json")
    
    def test_load_brewery_config_invalid_json(self):
        """Test loading config with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            with pytest.raises(json.JSONDecodeError):
                load_brewery_config(temp_path)
        finally:
            Path(temp_path).unlink()
    
    def test_format_events_output_with_events(self, sample_cli_events):
        """Test formatting events for output."""
        output = format_events_output(sample_cli_events)
        
        assert "Found 2 food truck events:" in output
        assert "Amazing BBQ Truck" in output
        assert "Taco Supreme" in output
        assert "Test Brewery" in output
        assert "🚚" in output  # Food truck emoji
        assert "📅" in output  # Calendar emoji
    
    def test_format_events_output_no_events(self):
        """Test formatting when no events are found."""
        output = format_events_output([])
        
        assert "No food truck events found" in output
    
    def test_format_events_output_with_errors(self, sample_cli_events):
        """Test formatting with both events and errors."""
        brewery = Brewery("failed-brewery", "Failed Brewery", "https://example.com")
        errors = [
            ScrapingError(brewery, "Network Timeout", "Connection timed out"),
            ScrapingError(brewery, "Parser Error", "Failed to parse HTML")
        ]
        
        output = format_events_output(sample_cli_events, errors)
        
        assert "Found 2 food truck events:" in output
        assert "⚠️  Processing Summary:" in output
        assert "✅ 2 events found successfully" in output
        assert "❌ 2 breweries failed" in output
        assert "❌ Errors:" in output
        assert "Failed Brewery: Connection timed out" in output
        assert "Failed Brewery: Failed to parse HTML" in output
    
    def test_format_events_output_only_errors(self):
        """Test formatting when only errors occur."""
        brewery = Brewery("failed-brewery", "Failed Brewery", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Network failed")]
        
        output = format_events_output([], errors)
        
        assert "❌ No events found - all breweries failed" in output
        assert "❌ Errors:" in output
        assert "Failed Brewery: Network failed" in output
    
    def test_format_events_output_instagram_fallback(self):
        """Test formatting Instagram fallback events."""
        future_date = datetime.now() + timedelta(days=1)
        instagram_event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Check Instagram @TestBrewery",
            date=future_date,
            description="Food truck schedule not available on website - check Instagram"
        )
        
        output = format_events_output([instagram_event])
        
        assert "❌ Check Instagram @TestBrewery" in output
        assert "check Instagram" in output
    
    def test_format_events_output_ai_generated_name(self):
        """Test formatting events with AI-generated vendor names."""
        future_date = datetime.now() + timedelta(days=1)
        ai_event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Georgia's",
            date=future_date,
            start_time=future_date.replace(hour=12),
            end_time=future_date.replace(hour=20),
            description="Greek food",
            ai_generated_name=True
        )
        regular_event = FoodTruckEvent(
            brewery_key="test-brewery",
            brewery_name="Test Brewery",
            food_truck_name="Taco Supreme",
            date=future_date,
            start_time=future_date.replace(hour=11),
            end_time=future_date.replace(hour=21),
            ai_generated_name=False
        )
        
        output = format_events_output([ai_event, regular_event])
        
        # AI-generated name should have emoji indicators
        assert "🚚 Georgia's 🖼️🤖 @ Test Brewery" in output
        # Regular name should not have emoji indicators
        assert "🚚 Taco Supreme @ Test Brewery" in output
        # Ensure no AI emojis for regular events
        assert "Taco Supreme 🖼️🤖" not in output
    
    @pytest.mark.asyncio
    async def test_scrape_food_trucks_success(self, temp_config_file, sample_cli_events):
        """Test successful food truck scraping."""
        with patch('around_the_grounds.main.ScraperCoordinator') as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.scrape_all = AsyncMock(return_value=sample_cli_events)
            mock_coordinator.get_errors = Mock(return_value=[])
            mock_coordinator_class.return_value = mock_coordinator
            
            events, errors = await scrape_food_trucks(temp_config_file)
            
            assert len(events) == 2
            assert len(errors) == 0
            assert events[0].food_truck_name == "Amazing BBQ Truck"
    
    @pytest.mark.asyncio
    async def test_scrape_food_trucks_with_errors(self, temp_config_file):
        """Test scraping with some errors."""
        brewery = Brewery("failed", "Failed", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Failed")]
        
        with patch('around_the_grounds.main.ScraperCoordinator') as mock_coordinator_class:
            mock_coordinator = Mock()
            mock_coordinator.scrape_all = AsyncMock(return_value=[])
            mock_coordinator.get_errors = Mock(return_value=errors)
            mock_coordinator_class.return_value = mock_coordinator
            
            events, returned_errors = await scrape_food_trucks(temp_config_file)
            
            assert len(events) == 0
            assert len(returned_errors) == 1
    
    @pytest.mark.asyncio
    async def test_scrape_food_trucks_no_breweries(self):
        """Test scraping with no breweries configured."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"breweries": []}, f)
            temp_path = f.name
        
        try:
            events, errors = await scrape_food_trucks(temp_path)
            assert len(events) == 0
            assert len(errors) == 0
        finally:
            Path(temp_path).unlink()
    
    def test_main_success(self, temp_config_file, sample_cli_events, capsys):
        """Test successful main function execution."""
        with patch('around_the_grounds.main.asyncio.run') as mock_run:
            mock_run.return_value = (sample_cli_events, [])
            
            exit_code = main(['--config', temp_config_file])
            
            assert exit_code == 0
            captured = capsys.readouterr()
            assert "🍺 Around the Grounds - Food Truck Tracker" in captured.out
            assert "Found 2 food truck events:" in captured.out
    
    def test_main_complete_failure(self, temp_config_file, capsys):
        """Test main function with complete failure."""
        brewery = Brewery("failed", "Failed", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Failed")]
        
        with patch('around_the_grounds.main.asyncio.run') as mock_run:
            mock_run.return_value = ([], errors)
            
            exit_code = main(['--config', temp_config_file])
            
            assert exit_code == 1  # Complete failure
            captured = capsys.readouterr()
            assert "❌ No events found - all breweries failed" in captured.out
    
    def test_main_partial_failure(self, temp_config_file, sample_cli_events, capsys):
        """Test main function with partial failure."""
        brewery = Brewery("failed", "Failed", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Failed")]
        
        with patch('around_the_grounds.main.asyncio.run') as mock_run:
            mock_run.return_value = (sample_cli_events, errors)
            
            exit_code = main(['--config', temp_config_file])
            
            assert exit_code == 2  # Partial success
            captured = capsys.readouterr()
            assert "Found 2 food truck events:" in captured.out
            assert "⚠️  Processing Summary:" in captured.out
    
    def test_main_critical_error(self, temp_config_file, capsys):
        """Test main function with critical error."""
        with patch('around_the_grounds.main.asyncio.run') as mock_run:
            mock_run.side_effect = Exception("Critical error occurred")
            
            exit_code = main(['--config', temp_config_file])
            
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Critical Error: Critical error occurred" in captured.out
    
    def test_main_verbose_mode(self, temp_config_file, capsys):
        """Test main function in verbose mode."""
        with patch('around_the_grounds.main.asyncio.run') as mock_run:
            mock_run.side_effect = Exception("Test error")
            
            exit_code = main(['--config', temp_config_file, '--verbose'])
            
            assert exit_code == 1
            captured = capsys.readouterr()
            # Should show traceback in verbose mode
            assert "Traceback" in captured.out or "Test error" in captured.out
    
    def test_main_version_flag(self, capsys):
        """Test main function with version flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(['--version'])
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out
    
    def test_main_help_flag(self, capsys):
        """Test main function with help flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(['--help'])
        
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Track food truck schedules" in captured.out
        assert "--config" in captured.out
        assert "--verbose" in captured.out
    
    def test_main_invalid_config_file(self, capsys):
        """Test main function with invalid config file."""
        exit_code = main(['--config', '/nonexistent/config.json'])
        
        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Critical Error:" in captured.out
        assert "not found" in captured.out
    
    def test_main_default_config(self, capsys):
        """Test main function using default config path."""
        with patch('around_the_grounds.main.load_brewery_config') as mock_load:
            mock_load.side_effect = FileNotFoundError("Config not found")
            
            exit_code = main([])
            
            assert exit_code == 1
            # Should try to load default config
            mock_load.assert_called_once_with(None)
    
    @pytest.mark.asyncio
    async def test_main_integration_end_to_end(self, temp_config_file):
        """Test end-to-end integration without mocking."""
        # This test uses real components but mocks the network calls
        from aioresponses import aioresponses
        
        # Mock the network responses for both breweries
        test_html = """
        <html><body>
            <div class="food-truck-entry">
                <h4>Fri 07.05</h4>
                <p>1 — 8pm</p>
                <p>Integration Test Truck</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            # Mock responses for both test breweries
            m.get("https://example1.com/food-trucks", status=200, body=test_html)
            m.get("https://example2.com/food-trucks", status=200, body=test_html)
            
            # Note: This would require actual parser implementations
            # that can handle the test URLs from the config
            # For now, this documents the integration test structure