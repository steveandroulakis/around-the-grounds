"""Pytest configuration and shared fixtures."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator, Dict

import aiohttp
import pytest

from around_the_grounds.models import Brewery, FoodTruckEvent


@pytest.fixture
def sample_brewery() -> Brewery:
    """Sample brewery for testing."""
    return Brewery(
        key="test-brewery",
        name="Test Brewery",
        url="https://example.com/food-trucks",
        parser_config={"test": "config"},
    )


@pytest.fixture
def sample_food_truck_event() -> FoodTruckEvent:
    """Sample food truck event for testing."""
    return FoodTruckEvent(
        brewery_key="test-brewery",
        brewery_name="Test Brewery",
        food_truck_name="Test Food Truck",
        date=datetime.now() + timedelta(days=1),
        start_time=datetime.now() + timedelta(days=1, hours=12),
        end_time=datetime.now() + timedelta(days=1, hours=20),
        description="Test event description",
    )


@pytest.fixture
def fixtures_dir() -> Path:
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def html_fixtures_dir(fixtures_dir: Path) -> Path:
    """Get the HTML fixtures directory path."""
    return fixtures_dir / "html"


@pytest.fixture
def config_fixtures_dir(fixtures_dir: Path) -> Path:
    """Get the config fixtures directory path."""
    return fixtures_dir / "config"


@pytest.fixture
async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession, None]:
    """Create an aiohttp session for testing."""
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def mock_html_response() -> str:
    """Mock HTML response for testing."""
    return """
    <html>
        <body>
            <div class="food-truck-entry">
                <h4>Sat 07.05</h4>
                <p>1 — 8pm</p>
                <p>Test Food Truck</p>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def empty_html_response() -> str:
    """Empty HTML response for testing."""
    return "<html><body></body></html>"


@pytest.fixture
def malformed_html_response() -> str:
    """Malformed HTML response for testing."""
    return "<html><body><div>Incomplete content"


@pytest.fixture
def future_date() -> datetime:
    """A date in the future for testing."""
    return datetime.now() + timedelta(days=3)


@pytest.fixture
def past_date() -> datetime:
    """A date in the past for testing."""
    return datetime.now() - timedelta(days=1)


@pytest.fixture
def test_breweries_config() -> Dict[str, Any]:
    """Test breweries configuration."""
    return {
        "breweries": [
            {
                "key": "test-brewery-1",
                "name": "Test Brewery 1",
                "url": "https://example1.com/food-trucks",
                "parser_config": {"test": "config1"},
            },
            {
                "key": "test-brewery-2",
                "name": "Test Brewery 2",
                "url": "https://example2.com/food-trucks",
                "parser_config": {"test": "config2"},
            },
        ]
    }
