# Haiku Generator

The system includes AI-powered haiku generation to create contextual, poetic descriptions of daily event scenes. Currently used only for the Ballard food trucks site (other sites set `generate_description: false` in their site config).

## Overview

The haiku generator uses **Claude Sonnet 4.6** (`claude-sonnet-4-6`) at `temperature=0.85` to create haikus that:
- Are **grounded in real-time weather data** from Open-Meteo (free, no API key)
- Incorporate time-of-day awareness (afternoon/evening/next-day forecasts)
- Feature a specific event and venue combination
- Capture the atmosphere of Ballard's local brewery + food truck culture
- Follow traditional 5-7-5 syllable structure
- Include inline emojis for visual appeal
- Explicitly avoid inventing sensory details not supported by the weather data

Weather is **required** — if the Open-Meteo fetch fails or returns no data, the haiku generator returns `None` and the system continues without a haiku (graceful degradation).

## How It Works

### Generation Process

1. **Weather Fetch**: `utils/weather.py` calls Open-Meteo for the configured lat/lon (default Ballard, Seattle) and picks an appropriate forecast window based on current Pacific time:
   - Before 6pm PT → afternoon forecast for today
   - 6–9pm PT → evening forecast for today
   - 9pm–midnight PT → afternoon forecast for tomorrow
   - After midnight → afternoon forecast for today (new calendar day)
2. **Date + Time-of-Day Context**: System passes the current date and derived time-of-day label to the prompt
3. **Random Event Selection**: One event is randomly selected from today's events
4. **Prompt Rendering**: Template in `config/haiku_prompt.txt` is rendered with `{date}`, `{time_of_day}`, `{weather}`, `{truck_name}`, `{venue_name}`, `{events_summary}` placeholders
5. **AI Generation**: Claude creates a contextual haiku featuring the selected event, venue, and weather-driven imagery
6. **Validation**: System ensures haiku has exactly 3 text lines with inline emojis
7. **Retry Logic**: If generation fails, system retries with exponential backoff (max 2 retries); weather failures are **not** retried and return `None` immediately

### Example Haikus

**Autumn**:
```
🍂 Autumn mist rolls in—
Plaza Garcia's warmth glows
at Obec's wood door 🍺
```

**Summer**:
```
☀️ Summer sun beams bright
Where Ya At Matt hangs at Stoup,
Hops drank with good eats 🍺
```

**Winter**:
```
❄️ Winter chill outside
Georgia's Greek warms the cold night
at Urban Family 🍺
```

## Configuration

### Environment Variables

```bash
# Required for haiku generation
export ANTHROPIC_API_KEY="your-api-key"

# Optional: override the prompt template file
export HAIKU_PROMPT_FILE="/path/to/custom_prompt.txt"

# Optional: override the weather fetch location (default: Ballard, Seattle)
export WEATHER_LOCATION_LAT="47.6689"
export WEATHER_LOCATION_LON="-122.3841"
```

Open-Meteo does not require an API key — the weather fetch works out of the box.

### Enabling/Disabling

Haiku generation is automatic when:
- `ANTHROPIC_API_KEY` is set in environment
- The site config has `generate_description: true` (default for ballard-food-trucks)
- Events are available for today
- System successfully connects to Claude API

If API key is not set or API fails, system gracefully continues without haikus.

### Prompt Template

The haiku prompt text now lives in an external template file so it can be tailored for other cities, venues, or languages without code changes.

- **Default location**: `around_the_grounds/config/haiku_prompt.txt`
- **Override via environment**: set `HAIKU_PROMPT_FILE=/path/to/custom_prompt.txt`
- **Override in code**: pass `HaikuGenerator(prompt_path="/path/to/custom_prompt.txt")`

The template uses Python `{format}` placeholders. The following fields are available:

| Placeholder | Description |
|-------------|-------------|
| `{date}` | Human-friendly date string (`March 15, 2025 (Saturday)`) |
| `{time_of_day}` | One of `Afternoon`, `Evening`, `Night` (derived from Pacific time) |
| `{weather}` | Formatted weather summary (e.g. `53°F, overcast, light breeze, 66% humidity`) |
| `{truck_name}` | Event title selected for featured focus |
| `{venue_name}` | Venue hosting the featured event |
| `{events_summary}` | Bullet list with the single randomly highlighted event/venue |

If the custom template is missing a placeholder, the generator falls back to the built-in default to avoid runtime failures. Keep the emoji formatting rules or adjust them to match your brand voice. If your custom template omits `{weather}` or `{time_of_day}`, the weather fetch still runs — the placeholders just aren't interpolated into your prompt.

## Usage

### In CLI Application

Haikus are automatically generated when running the scraper:

```bash
# Run with haiku generation
export ANTHROPIC_API_KEY="your-api-key"
uv run around-the-grounds

# Output includes:
# ✅ Stoup Brewing (5 events)
# ✅ Urban Family (3 events)
#
# 🎋 Today's Haiku:
# 🍂 Autumn mist rolls in—
# Plaza Garcia's warmth glows
# at Obec's wood door 🍺
```

### In Web Interface

Generated haikus are included in the web data and displayed prominently:

```json
{
  "haiku": "🍂 Autumn mist rolls in—\nPlaza Garcia's warmth glows\nat Obec's wood door 🍺",
  "events": [...]
}
```

### Programmatic Usage

```python
from around_the_grounds.utils.haiku_generator import HaikuGenerator
from datetime import datetime

# Initialize generator
generator = HaikuGenerator(api_key="your-api-key")

# Generate haiku for today's events
haiku = await generator.generate_haiku(
    date=datetime.now(),
    events=events
)

if haiku:
    print(f"🎋 Today's Haiku:\n{haiku}")
```

## Implementation Details

### HaikuGenerator Class

Located in `around_the_grounds/utils/haiku_generator.py`

**Key methods**:
- `generate_haiku(date, events, max_retries)`: Main entry point for haiku generation
- `_generate_haiku_internal(date, events)`: Internal API call handler
- `_clean_haiku(haiku)`: Validation and formatting of generated haikus

**Features**:
- Async API integration using `anthropic.AsyncAnthropic` (non-blocking in the async pipeline)
- Retry logic with exponential backoff (2^attempt seconds) on `APITimeoutError`
- Comprehensive error handling for API failures
- Weather fetched via `utils/weather.py` (Open-Meteo, cached time-of-day logic)
- Validation ensures 3-line structure with text content
- Automatic emoji formatting (inline with text)
- Early-return with `None` when weather fetch fails (graceful degradation — no haiku, but scraping and deploy continue normally)

### Prompt Engineering

The haiku prompt includes:
- Current date and day of week
- Time of day (Afternoon/Evening/Night)
- Current weather summary from Open-Meteo
- Selected event title and venue name
- Specific formatting requirements (5-7-5 syllables, inline emojis)
- Explicit guidance to avoid inventing sensory details not supported by the weather (no "damp" unless raining, no "misty" unless foggy, etc.)
- Guidance on Pacific Northwest atmosphere and food culture (Ballard-specific)
- Multiple examples of well-formatted haikus for different weather/time conditions

### Model Configuration

```python
message = await self.client.messages.create(
    model="claude-sonnet-4-6",          # Claude Sonnet 4.6
    max_tokens=150,                     # Sufficient for haiku + formatting
    temperature=0.85,                   # Higher creativity for poetry
    messages=[{"role": "user", "content": prompt}]
)
```

## Error Handling

### Retry Logic

```python
for attempt in range(max_retries + 1):
    try:
        haiku = await self._generate_haiku_internal(date, events)
        return haiku
    except anthropic.APITimeoutError:
        if attempt < max_retries:
            await asyncio.sleep(2**attempt)  # 1s, 2s, 4s
            continue
    except anthropic.APIError as e:
        self.logger.error(f"Anthropic API error: {str(e)}")
        break
```

### Error Types

- **APITimeoutError**: Network timeout → Retry with exponential backoff
- **APIError**: API failure (rate limit, auth, etc.) → Immediate failure, no retry
- **ValueError**: Incomplete haiku → Retry (treated as generation failure)
- **General Exception**: Unexpected error → Retry once, then fail

### Graceful Degradation

If haiku generation fails completely:
- System continues normal operation
- Web interface doesn't show haiku section
- CLI doesn't display haiku
- No impact on food truck data scraping or deployment

## Testing

### Mocking in Tests

Always mock the haiku generator in tests:

```python
@patch('around_the_grounds.utils.haiku_generator.HaikuGenerator.generate_haiku')
async def test_with_haiku(mock_haiku):
    mock_haiku.return_value = "🍂 Test haiku line one\nTest haiku line two here\nTest haiku line three 🍺"

    # ... test code

    mock_haiku.assert_called_once()
```

### Testing Haiku Validation

```python
def test_clean_haiku_valid():
    generator = HaikuGenerator()

    # Valid haiku with inline emojis
    haiku = "🍂 Line one here\nLine two in middle\nLine three at end 🍺"
    result = generator._clean_haiku(haiku)
    assert result == haiku

def test_clean_haiku_invalid():
    generator = HaikuGenerator()

    # Invalid: only 2 lines
    haiku = "🍂 Line one\nLine two 🍺"
    result = generator._clean_haiku(haiku)
    assert result is None
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_haiku_generation_integration():
    generator = HaikuGenerator()

    # Use real API (requires ANTHROPIC_API_KEY)
    events = [sample_event]
    haiku = await generator.generate_haiku(
        date=datetime.now(),
        events=events
    )

    assert haiku is not None
    assert len(haiku.split('\n')) == 3
    assert any(c.isalnum() for c in haiku)  # Contains text
```

## Best Practices

1. **Always set API key**: Haiku generation requires valid Anthropic API key
2. **Handle None returns**: Generator returns `None` on failure, handle gracefully
3. **Mock in tests**: Avoid API calls in automated tests
4. **Log appropriately**: Use INFO for successful generation, WARNING/ERROR for failures
5. **Don't block on failure**: Haiku generation is optional, don't fail entire scraping run
6. **Respect rate limits**: Haiku generator respects Anthropic API rate limits
7. **Cache when appropriate**: Consider caching haikus for same date/events to reduce API calls

## Performance Considerations

### API Call Timing

- **Single haiku per run**: Only one haiku generated per scraping run (not per venue)
- **Async operation**: Uses async API client for non-blocking operation
- **Timeout protection**: Configurable timeout prevents hanging (default: 30s via retry logic)
- **Minimal overhead**: Haiku generation adds ~1-2 seconds to total run time

### Cost Optimization

- **One API call per run**: Minimal API usage (one haiku per scraping operation)
- **Small token count**: Haikus are short, max_tokens=150 is sufficient
- **Smart retry logic**: Only retries on timeout, not on auth/rate limit errors
- **Early validation**: Text extraction attempted first before expensive API call

## Troubleshooting

### Haiku not generating

**Possible causes**:
- `ANTHROPIC_API_KEY` not set
- API key invalid or expired
- No events available for today
- API timeout or network issues

**Solutions**:
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Test with verbose logging
uv run around-the-grounds --verbose

# Check logs for haiku generation errors
# Look for: "Error generating haiku: ..."
```

### Haiku format invalid

**Possible causes**:
- Claude generated haiku with wrong format
- Emoji-only lines not filtered out
- Incomplete haiku (less than 3 lines)

**Solutions**:
- System automatically retries with cleaned prompt
- Validation filters out invalid formats
- Falls back gracefully if retries exhausted

### API rate limiting

**Possible causes**:
- Too many API calls in short time
- Anthropic API tier limits exceeded

**Solutions**:
- Space out scraping runs (use Temporal schedules with reasonable intervals)
- Consider caching haikus for same date
- Monitor API usage in Anthropic dashboard

## Future Enhancements

Potential improvements:
- Cache haikus by date to avoid regenerating same haiku multiple times
- Allow custom haiku themes via configuration
- Support multiple haikus per day (e.g., one per venue)
- Add haiku history/archive feature
- Integrate with social media posting
