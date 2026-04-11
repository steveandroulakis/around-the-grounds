# Error Handling Strategy

The application implements comprehensive error handling with these principles:

## Error Isolation

- **Individual venue failures don't affect others** - each venue is processed independently
- **Concurrent processing with isolation** - failures are captured per venue
- **Graceful degradation** - partial results are returned when some venues fail

### How It Works

The `ScraperCoordinator` processes venues concurrently using `asyncio.gather(..., return_exceptions=True)`:

```python
results = await asyncio.gather(*tasks, return_exceptions=True)

for i, result in enumerate(results):
    if isinstance(result, Exception):
        # Log error but continue processing other breweries
        self.logger.error(f"Failed to scrape {venues[i].name}: {str(result)}")
        failures.append((venues[i].name, result))
    else:
        # Add successful results
        all_events.extend(result)
```

This ensures that:
- One venue's failure doesn't crash the entire scraping process
- Users still get data from working venues
- All failures are logged for debugging

## Error Types & Handling

### Network Errors

**Types**: Timeouts, DNS failures, SSL issues, connection errors

**Handling**: Retry with exponential backoff (max 3 attempts)

```python
for attempt in range(max_retries):
    try:
        response = await session.get(url, timeout=timeout)
        return response
    except aiohttp.ClientError as e:
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
            continue
        raise
```

**Exit behavior**: Continue processing other venues

### HTTP Errors

**Types**: 404 (Not Found), 500 (Server Error), 403 (Forbidden), 503 (Service Unavailable)

**Handling**: Immediate failure with descriptive messages (no retry)

```python
if response.status >= 400:
    raise ValueError(f"HTTP {response.status}: {url}")
```

**Exit behavior**: Skip venue, continue with others

### Parser Errors

**Types**: Invalid HTML structure, missing elements, unexpected data formats

**Handling**: Validation and fallback logic, detailed logging

```python
try:
    container = soup.select_one('.event-container')
    if not container:
        raise ValueError("Missing event container element")
except Exception as e:
    self.logger.error(f"Parser error: {str(e)}")
    raise
```

**Exit behavior**: Skip venue, continue with others

### Vision API Errors

**Types**: Image analysis failures, API timeouts, rate limiting

**Handling**: Retry with exponential backoff, graceful degradation to "TBD"

```python
try:
    vision_name = await self.vision_analyzer.analyze_food_truck_image(url)
    return vision_name or "TBD"
except anthropic.APIError as e:
    self.logger.debug(f"Vision API error: {str(e)}")
    return "TBD"  # Graceful fallback
```

**Exit behavior**: Return "TBD", continue processing

### Configuration Errors

**Types**: Missing parsers, invalid URLs, malformed venue config

**Handling**: Immediate failure, no retry

```python
parser_class = ParserRegistry.get_parser(venue)
if not parser_class:
    raise ValueError(f"No parser for venue '{venue.key}' (source_type: '{venue.source_type}')")
```

**Exit behavior**: Skip venue, continue with others

### Data Validation Errors

**Types**: Invalid dates, missing required fields, malformed event data

**Handling**: Filter out invalid events, log for debugging

```python
def validate_event(event: Event) -> bool:
    if not event.title or event.title == "TBD":
        return False
    if not event.date or not event.time:
        return False
    return True

valid_events = [e for e in events if validate_event(e)]
```

**Exit behavior**: Continue with valid events only

## Error Reporting

### User-Friendly Output

Visual indicators and summary for end users:

```
✅ Stoup Brewing (5 events)
✅ Urban Family (3 events)
❌ Bale Breaker: HTTP 500 error
✅ Chuck's Hop Shop (4 events)

Summary: 12 events from 3/4 venues (1 failure)
```

### Detailed Logging

Debug information for troubleshooting (enabled with `--verbose` flag):

```python
self.logger.debug(f"Fetching URL: {url}")
self.logger.info(f"Parsed {len(events)} events from {venue.name}")
self.logger.warning(f"Vision analysis failed for {url}: {str(e)}")
self.logger.error(f"Failed to parse {venue.name}: {str(e)}")
```

**Logging levels**:
- `DEBUG`: Detailed execution flow (URL fetches, HTML parsing steps)
- `INFO`: Successful operations (event counts, completions)
- `WARNING`: Recoverable issues (vision analysis failures, validation warnings)
- `ERROR`: Failures requiring attention (network errors, parser crashes)

### Exit Codes

Communicate success/failure status to calling processes:

- **0**: Complete success (all breweries scraped successfully)
- **1**: Complete failure (no breweries could be scraped)
- **2**: Partial success (some venues failed, some succeeded)

```python
if all_events and failures:
    sys.exit(2)  # Partial success
elif not all_events:
    sys.exit(1)  # Complete failure
else:
    sys.exit(0)  # Complete success
```

## Retry Logic

### Exponential Backoff

Retries use exponential backoff to avoid overwhelming failing services:

```python
max_retries = 3
for attempt in range(max_retries):
    try:
        result = await operation()
        return result
    except RetryableError as e:
        if attempt < max_retries - 1:
            delay = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(delay)
            continue
        raise
```

### Selective Retrying

Only network/timeout errors are retried:

**Retry these**:
- `aiohttp.ClientError` (connection failures)
- `asyncio.TimeoutError` (request timeouts)
- `anthropic.APITimeoutError` (vision API timeouts)

**Don't retry these** (fail immediately):
- `ValueError` (parser/validation errors)
- HTTP 404/403 (resource not found/forbidden)
- Configuration errors (missing parser, invalid config)

### Retry Configuration

Retry behavior can be configured:

```python
# In ScraperCoordinator
coordinator = ScraperCoordinator(
    max_retries=3,           # Number of retry attempts
    timeout=30,              # Request timeout in seconds
    backoff_factor=2         # Exponential backoff multiplier
)

# In VisionAnalyzer
analyzer = VisionAnalyzer(
    max_retries=2,           # Vision API retry attempts
    timeout=30               # Vision API timeout
)
```

## Error Classification

### Retryable Errors

Temporary issues that may resolve on retry:
- Network timeouts
- Connection failures
- DNS resolution failures
- API rate limiting (429)
- Server errors (500, 503)

### Non-Retryable Errors

Permanent issues that won't resolve on retry:
- HTTP 404 (Not Found)
- HTTP 403 (Forbidden)
- Parser errors (invalid HTML structure)
- Configuration errors (missing parser, unsupported source_type)
- Validation errors (invalid data format)

### Critical vs. Non-Critical

**Critical errors** (stop processing venue):
- Missing parser registration (no specific or generic parser)
- Invalid venue configuration
- Fatal network errors (after retries exhausted)

**Non-critical errors** (continue processing):
- Single event validation failure
- Vision analysis timeout (falls back to "TBD")
- Missing optional fields

## Best Practices

When adding new parsers or features:

1. **Use BaseParser methods**: Inherit from `BaseParser` to get error handling automatically
2. **Log appropriately**: Use correct log levels (DEBUG, INFO, WARNING, ERROR)
3. **Validate early**: Check required fields before processing
4. **Fail gracefully**: Return empty lists instead of crashing on errors
5. **Test error scenarios**: Write tests for network failures, invalid data, timeouts
6. **Document error behavior**: Explain what happens when things fail
7. **Use type hints**: Help catch errors at type-check time
8. **Handle async exceptions**: Use try/except around async operations

### Example: Robust Parser Implementation

```python
class RobustParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        try:
            # Use BaseParser's fetch_page (includes retries)
            soup = await self.fetch_page(session, self.venue.url)

            # Validate HTML structure early
            container = soup.select_one('.container')
            if not container:
                raise ValueError("Missing container element")

            events = []
            for item in container.select('.event-item'):
                try:
                    # Extract and validate individual event
                    event = self._parse_event_item(item)
                    if self.validate_event(event):
                        events.append(event)
                    else:
                        self.logger.debug(f"Invalid event filtered out: {event}")
                except Exception as e:
                    # Log but continue processing other events
                    self.logger.warning(f"Failed to parse event: {str(e)}")
                    continue

            self.logger.info(f"Parsed {len(events)} valid events")
            return events

        except Exception as e:
            self.logger.error(f"Parser error: {str(e)}")
            raise  # Let coordinator handle venue-level failure
```
