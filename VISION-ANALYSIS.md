# AI Vision Analysis Integration

The system includes AI-powered vision analysis to extract food truck vendor names from logos and images when text-based methods fail.

## How It Works

1. **Text Extraction First**: All parsers attempt text-based vendor name extraction using existing methods
2. **Vision Fallback**: When text extraction fails, the system automatically analyzes event images using Claude Vision API
3. **Vendor Name Extraction**: The AI identifies business names from logos, signs, and food truck images
4. **Name Cleaning**: Extracted names are cleaned to remove common suffixes like "Food Truck", "Kitchen", etc.
5. **Graceful Degradation**: If vision analysis fails, the system falls back to "TBD"

## Configuration

Vision analysis is controlled by environment variables:

```bash
export ANTHROPIC_API_KEY="your-api-key"          # Required for vision analysis
export VISION_ANALYSIS_ENABLED="true"            # Enable/disable (default: true)
export VISION_MAX_RETRIES="2"                    # Max retry attempts (default: 2)
export VISION_TIMEOUT="30"                       # API timeout in seconds (default: 30)
```

## Usage in Parsers

The Urban Family parser demonstrates integration:

```python
from ..utils.vision_analyzer import VisionAnalyzer

class UrbanFamilyParser(BaseParser):
    def __init__(self, venue):
        super().__init__(venue)
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

## Testing Vision Analysis

Always mock vision analysis in tests to avoid API calls and ensure consistent results:

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

## Real-World Results

The vision analysis successfully extracts vendor names from actual venue images:

- **"Georgia's"** from Georgia's Greek Food Truck logo
- **"TOLU"** from Tolu Modern Fijian Cuisine branding
- **"Whateke"** from food truck signage

This eliminates many "TBD" entries and provides users with accurate vendor information.

## Implementation Details

### VisionAnalyzer Class

Located in `around_the_grounds/utils/vision_analyzer.py`, the `VisionAnalyzer` class provides:

- **Async API integration**: Uses `anthropic.AsyncAnthropic` for non-blocking image analysis
- **Retry logic**: Exponential backoff for API failures (configurable via environment variables)
- **Image validation**: URL validation before sending to API
- **Name cleaning**: Removes common suffixes ("Food Truck", "Kitchen", "Cuisine", etc.)
- **Error handling**: Graceful degradation on API errors or timeouts

### Error Handling

Vision analysis includes comprehensive error handling:

- **Network errors**: Retry with exponential backoff
- **API timeouts**: Configurable timeout values
- **Invalid images**: URL validation before API calls
- **API failures**: Graceful fallback to "TBD" or None
- **Rate limiting**: Respect Anthropic API rate limits

### Performance Considerations

- **Lazy initialization**: Vision analyzer is only created when needed
- **API calls only on fallback**: Text extraction is always tried first
- **Concurrent processing**: Works with async scraping coordinator
- **Timeout controls**: Prevent hanging on slow API responses

## Adding Vision Analysis to New Parsers

To add vision analysis to a new parser:

1. **Import VisionAnalyzer**:
   ```python
   from ..utils.vision_analyzer import VisionAnalyzer
   ```

2. **Add lazy initialization**:
   ```python
   def __init__(self, venue):
       super().__init__(venue)
       self._vision_analyzer = None

   @property
   def vision_analyzer(self):
       if self._vision_analyzer is None:
           self._vision_analyzer = VisionAnalyzer()
       return self._vision_analyzer
   ```

3. **Use as fallback in extraction logic**:
   ```python
   # Try text-based extraction first
   name = self._extract_from_text(item)
   if name:
       return name

   # Fall back to vision analysis
   if 'image_url' in item:
       try:
           vision_name = asyncio.run(
               self.vision_analyzer.analyze_food_truck_image(item['image_url'])
           )
           if vision_name:
               return vision_name
       except Exception as e:
           self.logger.debug(f"Vision analysis failed: {str(e)}")

   return "TBD"  # Final fallback
   ```

4. **Mock in tests**:
   ```python
   @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
   async def test_with_vision(self, mock_vision):
       mock_vision.return_value = "Expected Name"
       # ... test code
   ```
