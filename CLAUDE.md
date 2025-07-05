# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Around the Grounds is a robust Python CLI tool for tracking food truck schedules and locations across multiple breweries. The project features:
- **Async web scraping** with concurrent processing of multiple brewery websites
- **Extensible parser system** with custom parsers for different brewery website structures
- **Comprehensive error handling** with retry logic, isolation, and graceful degradation
- **Extensive test suite** with 157+ tests covering unit, integration, and error scenarios
- **Modern Python tooling** with uv for dependency management and packaging

## Development Commands

### Environment Setup
```bash
uv sync --dev  # Install all dependencies including dev tools
```

### Running the Application
```bash
uv run around-the-grounds              # Run the CLI tool
uv run around-the-grounds --verbose    # Run with verbose logging
uv run around-the-grounds --config /path/to/config.json  # Use custom config
```

### Testing
```bash
# Full test suite (157+ tests)
uv run python -m pytest                    # Run all tests
uv run python -m pytest tests/unit/        # Unit tests only
uv run python -m pytest tests/parsers/     # Parser-specific tests
uv run python -m pytest tests/integration/ # Integration tests
uv run python -m pytest tests/test_error_handling.py  # Error handling tests

# Test options
uv run python -m pytest -v                 # Verbose output
uv run python -m pytest --cov=around_the_grounds --cov-report=html  # Coverage
uv run python -m pytest -k "test_error"    # Run error-related tests
uv run python -m pytest -x                 # Stop on first failure
```

### Code Quality
```bash
uv run black .             # Format code
uv run isort .             # Sort imports
uv run flake8             # Lint code
uv run mypy around_the_grounds/  # Type checking
```

## Architecture

The project follows a modular architecture with clear separation of concerns:

```
around_the_grounds/
├── config/
│   └── breweries.json          # Brewery configurations
├── models/
│   ├── brewery.py              # Brewery data model  
│   └── schedule.py             # FoodTruckEvent data model
├── parsers/
│   ├── __init__.py             # Parser module exports
│   ├── base.py                 # Abstract base parser with error handling
│   ├── stoup_ballard.py        # Stoup Brewing parser
│   ├── bale_breaker.py         # Bale Breaker parser  
│   └── registry.py             # Parser registry/factory
├── scrapers/
│   └── coordinator.py          # Async scraping coordinator with error isolation
├── utils/
│   └── date_utils.py           # Date/time utilities with validation
└── main.py                     # CLI entry point with error reporting

tests/                          # Comprehensive test suite
├── conftest.py                 # Shared test fixtures
├── fixtures/
│   ├── html/                   # Real HTML samples from brewery websites
│   └── config/                 # Test configurations
├── unit/                       # Unit tests for individual components
├── parsers/                    # Parser-specific tests
├── integration/                # End-to-end integration tests
└── test_error_handling.py      # Comprehensive error scenario tests
```

### Key Components

- **Models**: Data classes for breweries and food truck events with validation
- **Parsers**: Extensible parser system with robust error handling and validation
  - `BaseParser`: Abstract base with HTTP error handling, validation, and logging
  - `StoupBallardParser`: Handles structured HTML with date/time parsing
  - `BaleBreakerParser`: Handles limited data with Instagram fallbacks
- **Registry**: Dynamic parser registration and retrieval with error handling
- **Scrapers**: Async coordinator with concurrent processing, retry logic, and error isolation
- **Config**: JSON-based configuration with validation and error reporting
- **Utils**: Date/time utilities with comprehensive parsing and validation
- **Tests**: 157+ tests covering all scenarios including extensive error handling

### Core Dependencies

**Production:**
- `aiohttp` - Async HTTP client for web scraping with timeout handling
- `beautifulsoup4` - HTML parsing with error tolerance
- `lxml` - Fast XML/HTML parser backend  
- `requests` - HTTP library (legacy support)

**Development & Testing:**
- `pytest` - Test framework with async support
- `pytest-asyncio` - Async test support
- `aioresponses` - HTTP response mocking for tests
- `pytest-mock` - Advanced mocking capabilities
- `freezegun` - Time mocking for date-sensitive tests
- `pytest-cov` - Code coverage reporting

The CLI is configured in `pyproject.toml` with entry point `around-the-grounds = "around_the_grounds.main:main"`.

## Adding New Breweries

To add a new brewery with proper error handling:

1. **Create Parser Class** in `parsers/` inheriting from `BaseParser`:
```python
from .base import BaseParser
from ..models import FoodTruckEvent
from typing import List
import aiohttp

class NewBreweryParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            soup = await self.fetch_page(session, self.brewery.url)
            events = []
            
            # Extract events from HTML with error handling
            # Use self.logger for debugging
            # Use self.validate_event() for data validation
            
            # Filter and validate all events before returning
            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events")
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing {self.brewery.name}: {str(e)}")
            raise ValueError(f"Failed to parse brewery website: {str(e)}")
```

2. **Register Parser** in `parsers/registry.py`:
```python
from .new_brewery import NewBreweryParser

class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        'new-brewery-key': NewBreweryParser,
        # ... existing parsers
    }
```

3. **Add Configuration** to `config/breweries.json`:
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

4. **Write Tests** in `tests/parsers/test_new_brewery.py`:
- Test successful parsing with mock HTML
- Test error scenarios (network, parsing, validation)
- Test with real HTML fixtures if available

## Error Handling Strategy

The application implements comprehensive error handling with these principles:

### Error Isolation
- **Individual brewery failures don't affect others** - each brewery is processed independently
- **Concurrent processing with isolation** - failures are captured per brewery
- **Graceful degradation** - partial results are returned when some breweries fail

### Error Types & Handling
- **Network Errors**: Timeouts, DNS failures, SSL issues → Retry with exponential backoff (max 3 attempts)
- **HTTP Errors**: 404, 500, 403 status codes → Immediate failure with descriptive messages  
- **Parser Errors**: Invalid HTML, missing elements → Validation and fallback logic
- **Configuration Errors**: Missing parsers, invalid URLs → No retry, immediate failure
- **Data Validation**: Invalid events → Filtered out, logged for debugging

### Error Reporting
- **User-friendly output**: Visual indicators (❌) for failures with summary
- **Detailed logging**: Debug info for troubleshooting with `--verbose` flag
- **Exit codes**: 0=success, 1=complete failure, 2=partial success

### Retry Logic
- **Exponential backoff**: 1s, 2s, 4s delays between retries
- **Selective retrying**: Only network/timeout errors are retried
- **Error classification**: Parser/config errors fail immediately

## Code Standards

- **Line length**: 88 characters (Black formatting)
- **Type hints**: Required throughout (`mypy` with `disallow_untyped_defs = true`)
- **Python compatibility**: 3.8+ required
- **Import sorting**: Black profile via isort
- **Async patterns**: async/await for all I/O operations
- **Error handling**: Comprehensive error handling and logging required
- **Testing**: All new code must include unit tests and error scenario tests
- **Logging**: Use class loggers (`self.logger`) with appropriate levels

## Testing Strategy

The project includes a comprehensive test suite with 157+ tests:

### Test Organization
```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── fixtures/                   # Test data and HTML samples
├── unit/                       # Unit tests for individual components
├── parsers/                    # Parser-specific functionality tests  
├── integration/                # End-to-end workflow tests
└── test_error_handling.py      # Comprehensive error scenario tests
```

### Test Coverage Areas
- **Models & Utilities**: Data validation, date parsing, registry operations
- **Parser Functionality**: HTML parsing, data extraction, validation logic  
- **Error Scenarios**: Network failures, malformed data, timeout handling
- **Integration Workflows**: CLI functionality, coordinator behavior, error reporting
- **Real Data Testing**: Uses actual HTML fixtures from brewery websites

### Writing Tests
- **Use real HTML fixtures** when possible (stored in `tests/fixtures/html/`)
- **Mock external dependencies** using `aioresponses` for HTTP calls
- **Test error scenarios** - every component should have error tests
- **Follow naming convention**: `test_[component]_[scenario]`
- **Use async tests** for async code with `@pytest.mark.asyncio`

### Running Tests
- **Quick feedback**: `uv run python -m pytest tests/unit/`
- **Parser-specific**: `uv run python -m pytest tests/parsers/`
- **Error scenarios**: `uv run python -m pytest -k "error"`
- **Integration**: `uv run python -m pytest tests/integration/`

## Development Workflow

When working on this project:

1. **Run tests first** to ensure current functionality works
2. **Write failing tests** for new features before implementation
3. **Implement with error handling** - always include try/catch and logging
4. **Test error scenarios** - network failures, invalid data, timeouts
5. **Run full test suite** before committing changes
6. **Update documentation** if adding new parsers or changing architecture

## Troubleshooting Common Issues

- **Parser not found**: Check `parsers/registry.py` registration
- **Network timeouts**: Adjust timeout in `ScraperCoordinator` constructor
- **Date parsing issues**: Check `utils/date_utils.py` patterns and add new formats
- **Test failures**: Use `pytest -v -s` for detailed output and debug prints
- **Import errors**: Ensure `__init__.py` files are present and imports are correct