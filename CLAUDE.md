# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Around the Grounds is a robust Python CLI tool for tracking food truck schedules and locations across multiple breweries. The project features:
- **Web interface** with mobile-responsive design and automatic deployment to Vercel
- **Async web scraping** with concurrent processing of multiple brewery websites
- **AI vision analysis** using Claude Vision API to extract vendor names from food truck logos/images
- **Auto-deployment** with git integration for seamless web updates
- **Extensible parser system** with custom parsers for different brewery website structures
- **Comprehensive error handling** with retry logic, isolation, and graceful degradation
- **Temporal workflow integration** with cloud deployment support (local, Temporal Cloud, custom servers)
- **Extensive test suite** with 196 tests covering unit, integration, vision analysis, and error scenarios
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
uv run around-the-grounds --preview    # Generate local preview files
uv run around-the-grounds --deploy     # Run and deploy to web

# With AI vision analysis (optional)
export ANTHROPIC_API_KEY="your-api-key"
uv run around-the-grounds --verbose    # Run with vision analysis enabled
uv run around-the-grounds --deploy     # Run with vision analysis and deploy to web
```

### Local Preview & Testing

Before deploying, generate and test web files locally:

```bash
# Generate web files locally for testing
uv run around-the-grounds --preview

# Serve locally and view in browser
cd public && python -m http.server 8000
# Visit: http://localhost:8000

# Automated testing methods:
# Test data.json endpoint
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | head -20 && pkill -f "python -m http.server" || true

# Test for specific event data (e.g., Sunday events)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | grep "2025-07-06" && pkill -f "python -m http.server" || true

# Test full homepage (basic connectivity)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/ > /dev/null && echo "✅ Homepage loads" && pkill -f "python -m http.server" || echo "❌ Homepage failed"

# Test JavaScript rendering (requires Node.js/puppeteer - optional)
# npm install -g puppeteer-cli
cd public && timeout 15s python -m http.server 8000 > /dev/null 2>&1 & sleep 2 && \
  node -e "
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.goto('http://localhost:8000');
  await page.waitForSelector('.day-section', {timeout: 5000});
  const dayHeaders = await page.$$eval('.day-header', els => els.map(el => el.textContent));
  console.log('✅ Rendered days:', dayHeaders.slice(0,2).join(', '));
  const eventCount = await page.$$eval('.truck-item', els => els.length);
  console.log('✅ Rendered events:', eventCount);
  await browser.close();
})().catch(e => console.log('❌ JS render test failed:', e.message));
" && pkill -f "python -m http.server" || echo "❌ Install puppeteer for JS testing: npm install -g puppeteer"
```

**What `--preview` does:**
- Scrapes fresh data from all brewery websites
- Copies templates from `public_template/` to `public/`
- Generates `data.json` with current food truck data
- Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.

### Client-Side Testing Strategy

The web interface performs critical JavaScript processing that must be tested beyond just raw `data.json`:

**JavaScript Processing Verified:**
- **Date grouping and sorting**: `eventsByDate` object creation
- **Timezone formatting**: `toLocaleDateString()` browser-specific rendering  
- **Emoji filtering**: Unicode removal from vendor names
- **DOM generation**: HTML injection and element creation
- **Event counting**: Final rendered item validation

**Why Headless Browser Testing Matters:**
- **Timezone bugs**: Server time vs. browser time differences (like the 5pm Sunday issue)
- **Locale-specific rendering**: Date formats vary by user's browser settings
- **JavaScript errors**: Runtime failures not caught by static testing
- **CSS rendering issues**: Missing elements due to styling problems
- **Real user experience**: Tests the complete data → display pipeline

**Puppeteer Testing Pattern:**
```javascript
// Wait for async data loading
await page.waitForSelector('.day-section', {timeout: 5000});

// Extract rendered content
const dayHeaders = await page.$$eval('.day-header', els => els.map(el => el.textContent));
const eventCount = await page.$$eval('.truck-item', els => els.length);

// Validate client-side processing
console.log('✅ Rendered days:', dayHeaders.slice(0,2).join(', '));
console.log('✅ Rendered events:', eventCount);
```

This approach catches issues that raw API testing misses and ensures users see the correct data.

### Web Deployment

**IMPORTANT**: Web deployment requires GitHub App authentication setup (see GitHub App Configuration section below).

```bash
# Deploy fresh data to website (full workflow)
uv run around-the-grounds --deploy

# Deploy to custom repository
uv run around-the-grounds --deploy --git-repo https://github.com/username/repo.git

# Or use environment variable
export GIT_REPOSITORY_URL="https://github.com/username/repo.git"
uv run around-the-grounds --deploy

# This command will:
# 1. Scrape all brewery websites for fresh data
# 2. Copy web templates from public_template/ to target repository
# 3. Generate web-friendly JSON data in target repository
# 4. Authenticate using GitHub App credentials
# 5. Commit and push complete website to target repository
# 6. Trigger automatic deployment (Vercel/Netlify/etc.)
# 7. Website updates live within minutes

# For Temporal workflows
uv run around-the-grounds --deploy --verbose  # Recommended for scheduled runs
```

### GitHub App Configuration

Web deployment uses GitHub App authentication for secure repository access:

#### 1. Create GitHub App
1. Go to https://github.com/settings/apps
2. Click "New GitHub App"
3. Configure:
   - **App name**: "Around the Grounds Deployer" (or similar)
   - **Homepage URL**: Your repository URL
   - **Repository permissions**:
     - Contents: Read & Write
     - Metadata: Read
   - **Where can this GitHub App be installed?**: Only on this account
4. **Generate private key** and download the `.pem` file
5. Note the **App ID** from the app settings page

#### 2. Install App on Repository
1. Go to your GitHub App settings
2. Click "Install App" 
3. Select your target repository (e.g., `ballard-food-trucks`)
4. Note the **Installation ID** from the URL after installation

#### 3. Configure Environment Variables
```bash
# Copy template
cp .env.example .env

# Add GitHub App credentials to .env:
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_APP_PRIVATE_KEY_B64=$(base64 -i path/to/your-app.private-key.pem)
GIT_REPOSITORY_URL=https://github.com/username/ballard-food-trucks.git

# Optional: AI vision analysis
ANTHROPIC_API_KEY=your-anthropic-api-key
```

#### 4. Target Repository Setup

The system pushes a complete static website to a **separate target repository** which is then deployed by platforms like Vercel:

**Two-Repository Architecture**:
- **Source repo** (this one): Contains scraping code, runs workers, web templates
- **Target repo** (e.g., `ballard-food-trucks`): Receives complete website, served as static site

**Configuration Options**:

**Default Repository**: `steveandroulakis/ballard-food-trucks`
```bash
# Uses default repository from settings
uv run around-the-grounds --deploy
```

**Custom Repository via CLI**:
```bash
uv run around-the-grounds --deploy --git-repo https://github.com/username/custom-repo.git
```

**Custom Repository via Environment**:
```bash
export GIT_REPOSITORY_URL="https://github.com/username/custom-repo.git"
uv run around-the-grounds --deploy
```

**Configuration Precedence**:
1. CLI argument (`--git-repo`)
2. Environment variable (`GIT_REPOSITORY_URL`)
3. Default (`steveandroulakis/ballard-food-trucks`)

#### 5. Deployment Workflow

When you run `--deploy`, the system:
1. **Scrapes** all brewery websites for fresh data
2. **Copies** web templates from `public_template/` to target repository
3. **Generates** web-friendly JSON data in target repository
4. **Authenticates** using GitHub App credentials
5. **Commits** and pushes complete website to target repository
6. **Triggers** automatic deployment (Vercel/Netlify/etc.)
7. **Website** updates live within minutes

### Temporal Workflow Execution

The system supports multiple Temporal deployment scenarios through environment-based configuration:

#### Local Development (Default)
```bash
# No configuration needed - connects to localhost:7233
# Start Temporal worker (run in separate terminal)
uv run python -m around_the_grounds.temporal.worker

# Execute workflow manually
uv run python -m around_the_grounds.temporal.starter --deploy --verbose

# Execute workflow with custom configuration
uv run python -m around_the_grounds.temporal.starter --config /path/to/config.json --deploy

# Execute workflow with custom ID for tracking
uv run python -m around_the_grounds.temporal.starter --workflow-id daily-update-2025 --deploy
```

#### Temporal Cloud Deployment
```bash
# Set environment variables for Temporal Cloud
export TEMPORAL_ADDRESS="your-namespace.acct.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_API_KEY="your-api-key"

# Start worker - automatically connects to Temporal Cloud
uv run python -m around_the_grounds.temporal.worker

# Execute workflows - uses cloud configuration
uv run python -m around_the_grounds.temporal.starter --deploy --verbose
```

### Production Deployment via CI/CD

For automated production updates using Docker and Watchtower:

```bash
# 1. GitHub Actions builds and pushes to Docker Hub (takes ~4 minutes)
# 2. Watchtower runs every 5 minutes to pull latest image
# 3. Monitor worker container:
ssh admin@192.168.0.20
docker ps -a -f "ancestor=steveandroulakis/around-the-grounds-worker:latest"
docker logs -f around-the-grounds-worker

# 4. Trigger schedule via Temporal UI and watch execution
```

**CI/CD Workflow:**
1. **Code changes** → GitHub Actions → Docker Hub (4 minutes)
2. **Watchtower** detects new image → pulls and restarts worker (every 5 minutes)
3. **Temporal schedules** trigger workflows → worker executes deployment
4. **Data deploys** automatically to target repository → live website updates

**Production Monitoring:**
- Monitor Docker containers on production server
- Check worker logs for execution status
- Trigger immediate updates via Temporal UI
- Verify deployment success on live website

#### Custom Server with mTLS
```bash
# Set environment variables for custom server with certificate authentication
export TEMPORAL_ADDRESS="your-server.example.com:7233"
export TEMPORAL_NAMESPACE="production"
export TEMPORAL_TLS_CERT="/path/to/cert.pem"
export TEMPORAL_TLS_KEY="/path/to/key.pem"

# Start worker and execute workflows
uv run python -m around_the_grounds.temporal.worker
uv run python -m around_the_grounds.temporal.starter --deploy
```

#### Environment Configuration
Create a `.env` file (based on `.env.example`) for persistent configuration:
```bash
# Copy the template
cp .env.example .env

# Edit with your Temporal configuration
# TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
# TEMPORAL_API_KEY=your-api-key
# etc.
```

#### Legacy CLI Arguments (Deprecated)
```bash
# CLI arguments still work but show deprecation warnings
uv run python -m around_the_grounds.temporal.starter --temporal-address production:7233 --deploy
# Warning: --temporal-address is deprecated, use TEMPORAL_ADDRESS environment variable
```

### Temporal Schedule Management

The system includes comprehensive schedule management for automated workflow execution:

#### Creating and Managing Schedules
```bash
# Create a schedule that runs every 30 minutes
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30

# Create a schedule with custom config and start paused
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id custom-scrape --interval 60 --config /path/to/config.json --paused

# List all schedules
uv run python -m around_the_grounds.temporal.schedule_manager list

# Describe a specific schedule
uv run python -m around_the_grounds.temporal.schedule_manager describe --schedule-id daily-scrape

# Pause/unpause schedules
uv run python -m around_the_grounds.temporal.schedule_manager pause --schedule-id daily-scrape --note "Maintenance window"
uv run python -m around_the_grounds.temporal.schedule_manager unpause --schedule-id daily-scrape

# Trigger immediate execution
uv run python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape

# Update schedule interval
uv run python -m around_the_grounds.temporal.schedule_manager update --schedule-id daily-scrape --interval 45

# Delete a schedule
uv run python -m around_the_grounds.temporal.schedule_manager delete --schedule-id daily-scrape
```

#### Schedule Features
- **Configurable intervals**: Any number of minutes (5, 30, 60, 120, etc.)
- **Multiple deployment modes**: Works with local, Temporal Cloud, and mTLS
- **Production ready**: Built-in error handling and detailed logging
- **Full lifecycle management**: Create, list, describe, pause, unpause, trigger, update, delete

### Testing
```bash
# Full test suite (196 tests)
uv run python -m pytest                    # Run all tests
uv run python -m pytest tests/unit/        # Unit tests only
uv run python -m pytest tests/parsers/     # Parser-specific tests
uv run python -m pytest tests/integration/ # Integration tests
uv run python -m pytest tests/unit/test_vision_analyzer.py  # Vision analysis tests
uv run python -m pytest tests/integration/test_vision_integration.py  # Vision integration tests
uv run python -m pytest tests/test_error_handling.py  # Error handling tests

# Test options
uv run python -m pytest -v                 # Verbose output
uv run python -m pytest --cov=around_the_grounds --cov-report=html  # Coverage
uv run python -m pytest -k "test_error"    # Run error-related tests
uv run python -m pytest -k "vision"        # Run vision-related tests
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
│   ├── breweries.json          # Brewery configurations
│   └── settings.py             # Vision analysis and other settings
├── models/
│   ├── brewery.py              # Brewery data model  
│   └── schedule.py             # FoodTruckEvent data model
├── parsers/
│   ├── __init__.py             # Parser module exports
│   ├── base.py                 # Abstract base parser with error handling
│   ├── stoup_ballard.py        # Stoup Brewing parser
│   ├── bale_breaker.py         # Bale Breaker parser
│   ├── urban_family.py         # Urban Family parser with vision analysis
│   └── registry.py             # Parser registry/factory
├── scrapers/
│   └── coordinator.py          # Async scraping coordinator with error isolation
├── temporal/                   # Temporal workflow integration
│   ├── __init__.py             # Module initialization
│   ├── workflows.py            # FoodTruckWorkflow definition
│   ├── activities.py           # ScrapeActivities and DeploymentActivities
│   ├── config.py               # Temporal client configuration system
│   ├── schedule_manager.py     # Comprehensive schedule management script
│   ├── shared.py               # WorkflowParams and WorkflowResult data classes
│   ├── worker.py               # Production-ready worker with error handling
│   ├── starter.py              # CLI workflow execution client
│   └── README.md               # Temporal-specific documentation
├── utils/
│   ├── date_utils.py           # Date/time utilities with validation
│   └── vision_analyzer.py      # AI vision analysis for vendor identification
└── main.py                     # CLI entry point with web deployment support

public_template/                # Web interface templates (copied to target repo)
├── index.html                  # Mobile-responsive web interface template
└── vercel.json                 # Vercel deployment configuration

public/                         # Generated files (git ignored)
└── data.json                   # Generated web data (not committed to source repo)

tests/                          # Comprehensive test suite
├── conftest.py                 # Shared test fixtures
├── fixtures/
│   ├── html/                   # Real HTML samples from brewery websites
│   └── config/                 # Test configurations
├── unit/                       # Unit tests for individual components
│   └── test_vision_analyzer.py # Vision analysis component tests
├── parsers/                    # Parser-specific tests
├── integration/                # End-to-end integration tests
│   └── test_vision_integration.py  # Vision analysis integration tests
└── test_error_handling.py      # Comprehensive error scenario tests
```

### Key Components

- **Models**: Data classes for breweries and food truck events with validation
- **Parsers**: Extensible parser system with robust error handling and validation
  - `BaseParser`: Abstract base with HTTP error handling, validation, and logging
  - `StoupBallardParser`: Handles structured HTML with date/time parsing
  - `BaleBreakerParser`: Handles limited data with Instagram fallbacks
  - `UrbanFamilyParser`: Hivey API integration with AI vision analysis fallback for vendor identification
- **Registry**: Dynamic parser registration and retrieval with error handling
- **Scrapers**: Async coordinator with concurrent processing, retry logic, and error isolation
- **Temporal**: Workflow orchestration for reliable execution and scheduling
  - `FoodTruckWorkflow`: Main workflow orchestrating scraping and deployment
  - `ScrapeActivities`: Activities wrapping existing scraping functionality
  - `DeploymentActivities`: Activities for web data generation and git operations
  - `FoodTruckWorker`: Production-ready worker with thread pool and signal handling
  - `FoodTruckStarter`: CLI client for manual workflow execution
  - `ScheduleManager`: Comprehensive schedule management with configurable intervals and full lifecycle operations
- **Config**: JSON-based configuration with validation and error reporting
- **Utils**: Date/time utilities with comprehensive parsing and validation, plus AI vision analysis
- **Web Interface**: Mobile-responsive HTML/CSS/JS frontend with automatic data fetching
- **Web Deployment**: Git-based deployment system with Vercel integration for automatic updates
- **Tests**: 196 tests covering all scenarios including extensive error handling and vision analysis

### Core Dependencies

**Production:**
- `aiohttp` - Async HTTP client for web scraping with timeout handling
- `beautifulsoup4` - HTML parsing with error tolerance
- `lxml` - Fast XML/HTML parser backend  
- `requests` - HTTP library (legacy support)
- `anthropic` - Claude Vision API for AI-powered image analysis
- `temporalio` - Temporal Python SDK for workflow orchestration

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
- Mock vision analysis if your parser uses it

## AI Vision Analysis Integration

The system includes AI-powered vision analysis to extract food truck vendor names from logos and images when text-based methods fail.

### How It Works

1. **Text Extraction First**: All parsers attempt text-based vendor name extraction using existing methods
2. **Vision Fallback**: When text extraction fails, the system automatically analyzes event images using Claude Vision API
3. **Vendor Name Extraction**: The AI identifies business names from logos, signs, and food truck images
4. **Name Cleaning**: Extracted names are cleaned to remove common suffixes like "Food Truck", "Kitchen", etc.
5. **Graceful Degradation**: If vision analysis fails, the system falls back to "TBD"

### Configuration

Vision analysis is controlled by environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"          # Required for vision analysis
export VISION_ANALYSIS_ENABLED="true"            # Enable/disable (default: true)
export VISION_MAX_RETRIES="2"                    # Max retry attempts (default: 2)
export VISION_TIMEOUT="30"                       # API timeout in seconds (default: 30)
```

### Usage in Parsers

The Urban Family parser demonstrates integration:

```python
from ..utils.vision_analyzer import VisionAnalyzer

class UrbanFamilyParser(BaseParser):
    def __init__(self, brewery):
        super().__init__(brewery)
        self._vision_analyzer = None
    
    @property
    def vision_analyzer(self):
        """Lazy initialization of vision analyzer."""
        if self._vision_analyzer is None:
            self._vision_analyzer = VisionAnalyzer()
        return self._vision_analyzer
    
    def _extract_food_truck_name(self, item: Dict[str, Any]) -> Optional[str]:
        # Try text-based extraction first
        name = self._extract_name_from_text_fields(item)
        if name:
            return name
        
        # Fall back to vision analysis if image available
        if 'eventImage' in item and item['eventImage']:
            try:
                vision_name = asyncio.run(
                    self.vision_analyzer.analyze_food_truck_image(item['eventImage'])
                )
                if vision_name:
                    return vision_name
            except Exception as e:
                self.logger.debug(f"Vision analysis failed: {str(e)}")
        
        return None
```

### Testing Vision Analysis

Always mock vision analysis in tests:

```python
@patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
async def test_parser_with_vision_fallback(self, mock_vision, parser):
    mock_vision.return_value = "Georgia's"
    
    test_item = {
        "eventTitle": "FOOD TRUCK",
        "eventImage": "https://example.com/logo.jpg"
    }
    
    result = parser._extract_food_truck_name(test_item)
    assert result == "Georgia's"
    mock_vision.assert_called_once_with("https://example.com/logo.jpg")
```

### Real-World Results

The vision analysis successfully extracts vendor names from actual brewery images:
- "Georgia's" from Georgia's Greek Food Truck logo
- "TOLU" from Tolu Modern Fijian Cuisine branding
- "Whateke" from food truck signage

This eliminates many "TBD" entries and provides users with accurate vendor information.

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
- **Vision API Errors**: Image analysis failures, API timeouts → Retry with exponential backoff, graceful degradation
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

The project includes a comprehensive test suite with 196 tests:

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
- **Vision Analysis**: AI image analysis, vendor name extraction, error handling, retry logic
- **Error Scenarios**: Network failures, malformed data, timeout handling, API failures
- **Integration Workflows**: CLI functionality, coordinator behavior, error reporting, vision integration
- **Real Data Testing**: Uses actual HTML fixtures from brewery websites and real image URLs

### Writing Tests
- **Use real HTML fixtures** when possible (stored in `tests/fixtures/html/`)
- **Mock external dependencies** using `aioresponses` for HTTP calls and `@patch` for vision analysis
- **Test error scenarios** - every component should have error tests (network, API, validation)
- **Mock vision analysis** - Use `@patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')` in tests
- **Follow naming convention**: `test_[component]_[scenario]`
- **Use async tests** for async code with `@pytest.mark.asyncio`

### Running Tests
- **Quick feedback**: `uv run python -m pytest tests/unit/`
- **Parser-specific**: `uv run python -m pytest tests/parsers/`
- **Vision analysis**: `uv run python -m pytest -k "vision"`
- **Error scenarios**: `uv run python -m pytest -k "error"`
- **Integration**: `uv run python -m pytest tests/integration/`

## Development Workflow

When working on this project:

1. **Run tests first** to ensure current functionality works
2. **Write failing tests** for new features before implementation
3. **Implement with error handling** - always include try/catch and logging
4. **Test error scenarios** - network failures, invalid data, timeouts
5. **Preview changes locally** using `--preview` flag before deployment
6. **Run full test suite** before committing changes
7. **Update documentation** if adding new parsers or changing architecture

### Local Development Workflow
```bash
# 1. Make code changes
# 2. Test locally with preview
uv run around-the-grounds --preview
cd public && python -m http.server 8000

# 3. Run tests
uv run python -m pytest

# 4. Deploy when ready
uv run around-the-grounds --deploy
```

## Web Deployment Workflow

When updating or maintaining the web interface:

### Development & Testing
1. **Test locally**: Ensure `uv run around-the-grounds` works correctly
2. **Test web templates**: Verify `public_template/` contains latest web interface files
3. **Test deployment**: Run `uv run around-the-grounds --deploy` (copies templates + generates data in target repo)
4. **Check responsive design**: Test on mobile viewport sizes

### Deployment Process
1. **Run deployment command**: `uv run around-the-grounds --deploy`
2. **Verify target repo**: Check that complete website was pushed to target repository
3. **Monitor Vercel deployment**: Changes should deploy automatically within minutes
4. **Test live site**: Verify website shows updated data and functions correctly

### Scheduled Updates (Temporal)
```python
# Recommended Temporal workflow execution
# The workflow runs the full pipeline: scrape → generate JSON → commit → deploy
# Execute via worker/starter pattern for reliability and monitoring

# Manual execution
uv run python -m around_the_grounds.temporal.starter --deploy --verbose

# Scheduled execution (configured via Temporal schedules)
# Create a schedule that runs every 30 minutes:
# uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30
# See around_the_grounds/temporal/README.md for complete schedule configuration
```

### Troubleshooting Web Deployment
- **No changes deployed**: Check if data actually changed or templates were updated
- **Website not updating**: Check Vercel deployment logs and ensure git push to target repo succeeded
- **Mobile display issues**: Test responsive CSS and ensure viewport meta tag is present in `public_template/`
- **Data fetching errors**: Verify `data.json` was generated correctly in target repository

## Troubleshooting Common Issues

- **Parser not found**: Check `parsers/registry.py` registration
- **Network timeouts**: Adjust timeout in `ScraperCoordinator` constructor
- **Date parsing issues**: Check `utils/date_utils.py` patterns and add new formats
- **Test failures**: Use `pytest -v -s` for detailed output and debug prints
- **Import errors**: Ensure `__init__.py` files are present and imports are correct