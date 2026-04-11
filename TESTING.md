# Testing Guide

This guide covers comprehensive testing strategies for the Around the Grounds project.

## Testing Commands

```bash
# Full test suite (499 tests)
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

## Client-Side Testing Strategy

The web interface performs critical JavaScript processing that must be tested beyond just raw `data.json`:

### JavaScript Processing Verified

- **Date grouping and sorting**: `eventsByDate` object creation
- **Timezone formatting**: `toLocaleDateString()` browser-specific rendering
- **Emoji filtering**: Unicode removal from vendor names
- **DOM generation**: HTML injection and element creation
- **Event counting**: Final rendered item validation

### Why Headless Browser Testing Matters

- **Timezone bugs**: Server time vs. browser time differences (like the 5pm Sunday issue)
- **Locale-specific rendering**: Date formats vary by user's browser settings
- **JavaScript errors**: Runtime failures not caught by static testing
- **CSS rendering issues**: Missing elements due to styling problems
- **Real user experience**: Tests the complete data → display pipeline

### Puppeteer Testing Pattern

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

### Automated Testing Methods

```bash
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

This approach catches issues that raw API testing misses and ensures users see the correct data.

## Testing Strategy

The project includes a comprehensive test suite with 499 tests:

### Test Organization

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── fixtures/                   # Test data and HTML samples
├── unit/                       # Unit tests for individual components
├── parsers/                    # Parser-specific tests (including generic parsers)
├── integration/                # End-to-end workflow tests
├── temporal/                   # Temporal workflow tests
└── test_error_handling.py      # Comprehensive error scenario tests
```

### Test Coverage Areas

- **Models & Utilities**: Data validation, date parsing, registry operations, site config loading
- **Parser Functionality**: HTML parsing, data extraction, validation logic (venue-specific + generic)
- **Generic Parsers**: WordPress REST API, HTML selector, AJAX/JSON API parsers
- **Vision Analysis**: AI image analysis, vendor name extraction, error handling, retry logic
- **Error Scenarios**: Network failures, malformed data, timeout handling, API failures
- **Integration Workflows**: CLI functionality, coordinator behavior, error reporting, vision integration
- **Temporal Workflows**: Activity serialization, workflow execution, schedule management
- **Real Data Testing**: Uses actual HTML fixtures from venue websites and real image URLs

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

## Test-Driven Development

When working on this project:

1. **Run tests first** to ensure current functionality works
2. **Write failing tests** for new features before implementation
3. **Implement with error handling** - always include try/catch and logging
4. **Test error scenarios** - network failures, invalid data, timeouts
5. **Preview changes locally** using `--preview` flag before deployment
6. **Run full test suite** before committing changes
7. **Update documentation** if adding new parsers or changing architecture
