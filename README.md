# Around the Grounds 🍺🚚

A Python tool for tracking food truck schedules and locations across multiple breweries. Get a unified view of food truck events for the next 7 days by scraping brewery websites asynchronously.

## Example Output

```
🍺 Around the Grounds - Food Truck Tracker
==================================================
Found 23 food truck events:

📅 Saturday, July 05, 2025
  🚚 Woodshop BBQ @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🚚 Kaosamai Thai @ Obec Brewing 04:00 PM - 08:00 PM
  🚚 The Cheese Pit @ Yonder Cider & Bale Breaker - Ballard

📅 Sunday, July 06, 2025
  🚚 Burger Planet @ Stoup Brewing - Ballard 01:00 PM - 07:00 PM
  🚚 Kaosamia @ Urban Family Brewing 01:00 PM - 07:00 PM
  🚚 Tacos & Beer @ Yonder Cider & Bale Breaker - Ballard

📅 Monday, July 07, 2025
  🚚 TBD @ Urban Family Brewing 04:00 PM - 08:00 PM
  🚚 Where Ya At Matt @ Stoup Brewing - Ballard 05:00 PM - 08:00 PM

📅 Tuesday, July 08, 2025
  🚚 TBD @ Urban Family Brewing 04:00 PM - 08:00 PM
  🚚 Poke Me @ Stoup Brewing - Ballard 05:00 PM - 08:00 PM
  🚚 Tolu Modern Fijian Cuisine @ Yonder Cider & Bale Breaker - Ballard

📅 Wednesday, July 09, 2025
  🚚 Impeckable Chicken @ Urban Family Brewing 04:00 PM - 08:00 PM
  🚚 Paparepas @ Stoup Brewing - Ballard 04:30 PM - 08:30 PM
  🚚 Georgia's Greek @ Yonder Cider & Bale Breaker - Ballard

📅 Thursday, July 10, 2025
  🚚 Birrieria Pepe El Toro @ Stoup Brewing - Ballard 12:00 PM - 04:00 PM
  🚚 TBD @ Urban Family Brewing 04:00 PM - 08:00 PM
  🚚 Impeckable Chicken @ Yonder Cider & Bale Breaker - Ballard

📅 Friday, July 11, 2025
  🚚 Georgia's Greek @ Stoup Brewing - Ballard 05:00 PM - 09:00 PM
  🚚 Now Make Me A Sandwich @ Yonder Cider & Bale Breaker - Ballard

📅 Saturday, July 12, 2025
  🚚 Don Luchos @ Stoup Brewing - Ballard
  🚚 Tat's Truck @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🚚 Oskar @ Urban Family Brewing 04:00 PM - 08:00 PM
  🚚 Georgia's Greek @ Yonder Cider & Bale Breaker - Ballard
```

## Features

- 🔄 **Async Web Scraping**: Concurrent scraping of multiple brewery websites
- 🌐 **API Integration**: Support for both HTML scraping and direct API access
- 🤖 **AI Vision Analysis**: Extracts food truck vendor names from logos/images using Claude Vision API
- 📅 **7-Day Forecast**: Shows food truck schedules for the next week
- 🏗️ **Extensible Parser System**: Easy to add new breweries with custom parsers
- ⚙️ **JSON Configuration**: Simple brewery configuration via JSON
- 🚀 **Fast Performance**: Concurrent processing with comprehensive error handling
- 🛡️ **Robust Error Handling**: Retry logic, error isolation, and graceful degradation
- 📊 **Formatted Output**: Clean, readable schedule display with emojis
- 🧪 **Comprehensive Testing**: 205+ tests covering all scenarios including error cases

## Supported Breweries

- **Stoup Brewing - Ballard**: Full HTML schedule parsing with date/time extraction
- **Yonder Cider & Bale Breaker - Ballard**: Squarespace API integration for calendar data
- **Obec Brewing**: Simple text-based food truck information parsing
- **Urban Family Brewing**: Hivey API integration with AI vision analysis for vendor identification

## Installation

From source:
```bash
git clone https://github.com/steveandroulakis/around-the-grounds
cd around-the-grounds
uv sync
```

## Usage

### Basic Usage
```bash
uv run around-the-grounds
```

### With Verbose Logging
```bash
uv run around-the-grounds --verbose
```

### Custom Configuration
```bash
uv run around-the-grounds --config /path/to/custom/breweries.json
```

### AI Vision Analysis Setup (Optional)
For enhanced vendor name extraction from images:
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
uv run around-the-grounds
```

When configured, the system will automatically analyze food truck logos to extract vendor names when text-based extraction fails, improving identification accuracy for breweries like Urban Family.

### Example Output
```
🍺 Around the Grounds - Food Truck Tracker
==================================================
Found 17 food truck events:

📅 Saturday, July 05, 2025
  🚚 Woodshop BBQ @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🚚 Kaosamai Thai @ Obec Brewing 04:00 PM - 08:00 PM
  🚚 The Cheese Pit @ Yonder Cider & Bale Breaker - Ballard

📅 Sunday, July 06, 2025
  🚚 Burger Planet @ Stoup Brewing - Ballard 01:00 PM - 07:00 PM
  🚚 Kaosamia @ Urban Family Brewing 01:00 PM - 07:00 PM
  🚚 Tacos & Beer @ Yonder Cider & Bale Breaker - Ballard
```

## Configuration

The tool uses a JSON configuration file to define brewery sources:

```json
{
  "breweries": [
    {
      "key": "stoup-ballard",
      "name": "Stoup Brewing - Ballard",
      "url": "https://www.stoupbrewing.com/ballard/",
      "parser_config": {
        "selectors": {
          "food_truck_entry": ".food-truck-day",
          "info_container": ".lunch-truck-info",
          "date": "h4",
          "time": ".hrs",
          "truck_name": ".truck"
        }
      }
    },
    {
      "key": "urban-family",
      "name": "Urban Family Brewing",
      "url": "https://app.hivey.io/urbanfamily/public-calendar",
      "parser_config": {
        "note": "Uses Hivey API endpoint for calendar data",
        "api_endpoint": "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar",
        "api_type": "hivey_calendar"
      }
    }
  ]
}
```

## Adding New Breweries

To add support for a new brewery:

1. **Create a Parser**: Implement a new parser class in `around_the_grounds/parsers/`
```python
from .base import BaseParser
from ..models import FoodTruckEvent
import aiohttp

class NewBreweryParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            # For HTML scraping
            soup = await self.fetch_page(session, self.brewery.url)
            
            # For API access (like Urban Family)
            # response = await session.get(api_url, headers=headers)
            # data = await response.json()
            
            events = []
            # Extract events from HTML or JSON
            # Use self.validate_event() for data validation
            
            valid_events = self.filter_valid_events(events)
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing {self.brewery.name}: {str(e)}")
            raise ValueError(f"Failed to parse brewery website: {str(e)}")
```

2. **Register the Parser**: Add it to `around_the_grounds/parsers/registry.py`
```python
from .new_brewery import NewBreweryParser

class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        'new-brewery-key': NewBreweryParser,
        'urban-family': UrbanFamilyParser,
        'stoup-ballard': StoupBallardParser,
        # ... existing parsers
    }
```

3. **Add Configuration**: Include the brewery in your `breweries.json`
```json
{
  "key": "new-brewery-key",
  "name": "New Brewery Name",
  "url": "https://newbrewery.com/food-trucks",
  "parser_config": {
    "selectors": {
      "container": ".food-truck-container",
      "date": ".date-element",
      "time": ".time-element"
    }
  }
}
```

4. **Write Tests**: Create tests in `tests/parsers/test_new_brewery.py`
```python
import pytest
from aioresponses import aioresponses
from around_the_grounds.parsers.new_brewery import NewBreweryParser

class TestNewBreweryParser:
    @pytest.mark.asyncio
    async def test_parse_success(self, parser, sample_html):
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=sample_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        
        assert len(events) > 0
        assert events[0].food_truck_name is not None
```

## Architecture

The project follows a clean, modular architecture with comprehensive error handling:

- **Models**: Data classes for breweries and food truck events with validation
- **Parsers**: Extensible parser system supporting HTML scraping, API integration, and AI vision analysis
  - `BaseParser`: Abstract base with HTTP error handling and validation
  - `StoupBallardParser`: HTML parsing with date/time extraction
  - `BaleBreakerParser`: Squarespace API integration
  - `ObecBrewingParser`: Simple text pattern matching
  - `UrbanFamilyParser`: Hivey API integration with AI vision fallback for vendor identification
- **Registry**: Dynamic parser registration and retrieval with error handling
- **Scrapers**: Async coordinator with concurrent processing, retry logic, and error isolation
- **Config**: JSON-based configuration with validation and error reporting
- **Utils**: Date/time utilities with comprehensive parsing and validation, plus AI vision analysis
- **Tests**: 205+ tests covering unit, integration, vision analysis, and error scenarios

## Development

### Setup
```bash
uv sync --dev
```

### Running Tests
```bash
uv run python -m pytest                    # Run all tests (205+ tests)
uv run python -m pytest -v                 # Verbose output
uv run python -m pytest --cov=around_the_grounds --cov-report=html  # Coverage
uv run python -m pytest tests/parsers/     # Parser-specific tests
uv run python -m pytest tests/integration/ # Integration tests
uv run python -m pytest tests/unit/test_vision_analyzer.py  # Vision analysis tests
uv run python -m pytest -k "test_error"    # Error handling tests
```

### Code Quality
```bash
uv run black .             # Format code
uv run isort .             # Sort imports
uv run flake8             # Lint code
uv run mypy around_the_grounds/  # Type checking
```

## Requirements

- Python 3.8+
- `aiohttp` - Async HTTP client
- `beautifulsoup4` - HTML parsing
- `lxml` - XML/HTML parser backend
- `anthropic` - AI Vision API for image analysis (optional)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your brewery parser
4. Include tests for your parser
5. Submit a pull request

## License

MIT License