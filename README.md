# Around the Grounds 🍺🚚

A Python tool for tracking food truck schedules and locations across multiple breweries. Get a unified view of food truck events for the next 7 days by scraping brewery websites asynchronously.

## Features

- 🔄 **Async Web Scraping**: Concurrent scraping of multiple brewery websites
- 📅 **7-Day Forecast**: Shows food truck schedules for the next week
- 🏗️ **Extensible Parser System**: Easy to add new breweries with custom parsers
- ⚙️ **JSON Configuration**: Simple brewery configuration via JSON
- 🚀 **Fast Performance**: Concurrent processing with proper error handling
- 📊 **Formatted Output**: Clean, readable schedule display with emojis

## Supported Breweries

- **Stoup Brewing - Ballard**: Full schedule parsing
- **Yonder Cider & Bale Breaker - Ballard**: Instagram reference (limited web data)

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

### Example Output
```
🍺 Around the Grounds - Food Truck Tracker
==================================================
Found 3 food truck events:

📅 Friday, July 05, 2025
  🚚 Woodshop BBQ @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM

📅 Saturday, July 06, 2025
  🚚 Taco Truck @ Stoup Brewing - Ballard 12:00 PM - 09:00 PM
  🚚 Check Instagram @BaleBreaker @ Yonder Cider & Bale Breaker - Ballard
     Food truck schedule not available on website - check Instagram
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
          "food_truck_entry": ".food-truck-entry",
          "date": "h4",
          "time": "p"
        }
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

class NewBreweryParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        soup = await self.fetch_page(session, self.brewery.url)
        # Parse the webpage and return FoodTruckEvent objects
        return events
```

2. **Register the Parser**: Add it to `around_the_grounds/parsers/registry.py`
```python
from .new_brewery import NewBreweryParser

class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        'new-brewery-key': NewBreweryParser,
        # ... existing parsers
    }
```

3. **Add Configuration**: Include the brewery in your `breweries.json`
```json
{
  "key": "new-brewery-key",
  "name": "New Brewery Name",
  "url": "https://newbrewery.com/food-trucks",
  "parser_config": {}
}
```

## Architecture

The project follows a clean, modular architecture:

- **Models**: Data classes for breweries and food truck events
- **Parsers**: Extensible parser system with base class and specific implementations  
- **Registry**: Dynamic parser registration for different brewery types
- **Scrapers**: Async coordinator for concurrent website scraping
- **Config**: JSON-based configuration for brewery definitions
- **Utils**: Shared utilities for date parsing and formatting

## Development

### Setup
```bash
uv sync --dev
```

### Running Tests
```bash
uv run pytest
uv run pytest -v          # Verbose output
uv run pytest --cov       # With coverage
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your brewery parser
4. Include tests for your parser
5. Submit a pull request

## License

MIT License