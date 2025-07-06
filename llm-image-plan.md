# LLM Image Analysis Plan for Food Truck Vendor Identification

## Overview

This plan outlines integrating Anthropic's Claude Vision API to extract food truck vendor names from images when text data is unavailable or unclear (e.g., showing "TBD" instead of "Georgia's").

## Problem Statement

Currently, when the Urban Family parser cannot extract a vendor name from JSON text fields, it falls back to "TBD" even when there's an `eventImage` URL that contains the vendor's logo/branding that could be analyzed.

Example case:
- JSON shows `"eventTitle": "FOOD TRUCK"` (generic)
- Image URL: `https://hivey-1.s3.us-east-1.amazonaws.com/uploads/MainlogoB_Webpreview_Georgia's.jpg`
- Current result: "TBD"
- Desired result: "Georgia's Greek Food Truck" (extracted via vision analysis)

## Implementation Plan

### 1. Add Anthropic Dependency

Add the `anthropic` package to pyproject.toml dependencies:

```toml
[project]
dependencies = [
    # ... existing dependencies
    "anthropic>=0.40.0",
]
```

Install with: `uv sync`

### 2. Create Vision Analysis Module

Create `around_the_grounds/utils/vision_analyzer.py`:

```python
import asyncio
import base64
import logging
from typing import Optional
import aiohttp
import anthropic


class VisionAnalyzer:
    """Analyzes food truck images to extract vendor names using Claude Vision API."""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(api_key=api_key)  # Uses ANTHROPIC_API_KEY env var if None
        self.logger = logging.getLogger(__name__)
    
    async def analyze_food_truck_image(self, image_url: str) -> Optional[str]:
        """
        Analyze a food truck image URL and extract the vendor name.
        
        Args:
            image_url: URL to the food truck image
            
        Returns:
            Extracted vendor name or None if analysis fails
        """
        try:
            # Check if image URL is valid and accessible
            if not self._is_valid_image_url(image_url):
                self.logger.debug(f"Invalid or inaccessible image URL: {image_url}")
                return None
            
            # Use URL-based image analysis (more efficient than downloading)
            vendor_name = await self._analyze_image_by_url(image_url)
            
            if vendor_name:
                self.logger.info(f"Extracted vendor name from image: '{vendor_name}'")
                return vendor_name
            else:
                self.logger.debug(f"Could not extract vendor name from image: {image_url}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error analyzing image {image_url}: {str(e)}")
            return None
    
    async def _analyze_image_by_url(self, image_url: str) -> Optional[str]:
        """Analyze image using Claude Vision API with URL."""
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "url",
                                    "url": image_url,
                                },
                            },
                            {
                                "type": "text",
                                "text": """Look at this food truck or restaurant logo/image. 
                                Extract ONLY the business name (e.g., "Georgia's", "Marination", "Paseo"). 
                                Do not include words like "Food Truck", "Kitchen", "Catering" unless they're part of the actual business name.
                                If you cannot clearly identify a business name, respond with "UNKNOWN".
                                Respond with just the business name, nothing else."""
                            }
                        ],
                    }
                ],
            )
            
            # Extract the response text
            response_text = message.content[0].text.strip()
            
            # Clean up the response
            if response_text and response_text.upper() != "UNKNOWN":
                # Remove common suffixes that aren't part of the business name
                cleaned_name = self._clean_vendor_name(response_text)
                return cleaned_name
            
            return None
            
        except Exception as e:
            self.logger.error(f"Claude Vision API error: {str(e)}")
            return None
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL appears to be a valid image URL."""
        if not url or not url.startswith(('http://', 'https://')):
            return False
        
        # Check for common image extensions or image hosting domains
        image_indicators = [
            '.jpg', '.jpeg', '.png', '.gif', '.webp',
            's3.amazonaws.com', 'images.', 'img.', 'media.'
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in image_indicators)
    
    def _clean_vendor_name(self, name: str) -> str:
        """Clean extracted vendor name to remove common suffixes."""
        name = name.strip()
        
        # Remove common business suffixes that Claude might include
        suffixes_to_remove = [
            'Food Truck', 'Kitchen', 'Catering', 'Restaurant', 'Cafe', 'Bar',
            'LLC', 'Inc', 'Co', 'Company', '&amp;', 'and Co'
        ]
        
        for suffix in suffixes_to_remove:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        
        return name
```

### 3. Integrate into Urban Family Parser

Modify `around_the_grounds/parsers/urban_family.py`:

```python
# Add import at top
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
    
    def _extract_food_truck_name(self, item: Dict[str, Any]) -> str:
        """
        Extract food truck name with vision analysis fallback.
        """
        # Try existing text-based extraction methods first
        name = self._extract_name_from_text_fields(item)
        if name:
            return name
        
        # If no name found from text, try image analysis
        if 'eventImage' in item and item['eventImage']:
            image_url = str(item['eventImage'])
            self.logger.debug(f"Attempting vision analysis for image: {image_url}")
            
            # Use asyncio to run the async vision analysis
            try:
                loop = asyncio.get_event_loop()
                vision_name = loop.run_until_complete(
                    self.vision_analyzer.analyze_food_truck_image(image_url)
                )
                if vision_name:
                    self.logger.info(f"Vision analysis extracted name: {vision_name}")
                    return vision_name
            except Exception as e:
                self.logger.debug(f"Vision analysis failed: {str(e)}")
        
        # Final fallback to TBD
        return "TBD"
    
    def _extract_name_from_text_fields(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract name from text fields (existing logic moved here)."""
        # Move existing logic from _extract_food_truck_name here
        # [All the existing text extraction logic from lines 154-215]
        # This keeps the existing functionality intact
        pass
```

### 4. Configuration and Environment

Add configuration options to handle vision analysis:

```python
# In around_the_grounds/config/settings.py (new file)
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class VisionConfig:
    enabled: bool = True
    max_retries: int = 2
    timeout_seconds: int = 30
    api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls):
        return cls(
            enabled=os.getenv('VISION_ANALYSIS_ENABLED', 'true').lower() == 'true',
            max_retries=int(os.getenv('VISION_MAX_RETRIES', '2')),
            timeout_seconds=int(os.getenv('VISION_TIMEOUT', '30')),
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )
```

### 5. Error Handling and Retry Logic

Enhance the vision analyzer with robust error handling:

```python
# In VisionAnalyzer class, add retry logic
async def analyze_food_truck_image(self, image_url: str, max_retries: int = 2) -> Optional[str]:
    """Analyze with retry logic for network issues."""
    for attempt in range(max_retries + 1):
        try:
            return await self._analyze_image_by_url(image_url)
        except anthropic.APITimeoutError:
            if attempt < max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                continue
            self.logger.warning(f"Vision analysis timed out after {max_retries} retries")
        except anthropic.APIError as e:
            self.logger.error(f"Anthropic API error: {str(e)}")
            break
        except Exception as e:
            if attempt < max_retries:
                await asyncio.sleep(1)
                continue
            self.logger.error(f"Vision analysis failed: {str(e)}")
    
    return None
```

### 6. Testing Implementation

#### Unit Tests (`tests/unit/test_vision_analyzer.py`):

```python
import pytest
from unittest.mock import Mock, patch, AsyncMock
from around_the_grounds.utils.vision_analyzer import VisionAnalyzer

class TestVisionAnalyzer:
    @pytest.fixture
    def vision_analyzer(self):
        return VisionAnalyzer()
    
    def test_is_valid_image_url(self, vision_analyzer):
        assert vision_analyzer._is_valid_image_url("https://example.com/image.jpg")
        assert vision_analyzer._is_valid_image_url("https://s3.amazonaws.com/bucket/image")
        assert not vision_analyzer._is_valid_image_url("not-a-url")
        assert not vision_analyzer._is_valid_image_url("")
    
    def test_clean_vendor_name(self, vision_analyzer):
        assert vision_analyzer._clean_vendor_name("Georgia's Food Truck") == "Georgia's"
        assert vision_analyzer._clean_vendor_name("Marination Kitchen") == "Marination"
        assert vision_analyzer._clean_vendor_name("Simple Name") == "Simple Name"
    
    @pytest.mark.asyncio
    @patch('anthropic.Anthropic')
    async def test_analyze_image_success(self, mock_anthropic, vision_analyzer):
        # Mock successful API response
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text="Georgia's")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        vision_analyzer.client = mock_client
        
        result = await vision_analyzer.analyze_food_truck_image("https://example.com/georgia.jpg")
        assert result == "Georgia's"
    
    @pytest.mark.asyncio
    @patch('anthropic.Anthropic')
    async def test_analyze_image_unknown_response(self, mock_anthropic, vision_analyzer):
        # Mock "UNKNOWN" response
        mock_client = Mock()
        mock_message = Mock()
        mock_message.content = [Mock(text="UNKNOWN")]
        mock_client.messages.create.return_value = mock_message
        mock_anthropic.return_value = mock_client
        
        vision_analyzer.client = mock_client
        
        result = await vision_analyzer.analyze_food_truck_image("https://example.com/unclear.jpg")
        assert result is None
```

#### Integration Tests (`tests/integration/test_vision_integration.py`):

```python
import pytest
from unittest.mock import Mock, patch
from around_the_grounds.parsers.urban_family import UrbanFamilyParser
from around_the_grounds.models.brewery import Brewery

class TestVisionIntegration:
    @pytest.fixture
    def parser(self):
        brewery = Brewery(key="urban-family", name="Urban Family", url="https://test.com")
        return UrbanFamilyParser(brewery)
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_vision_fallback_in_parser(self, mock_vision, parser):
        # Mock vision analysis returning a vendor name
        mock_vision.return_value = "Georgia's"
        
        # Test item with no text vendor name but has image
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/georgia-logo.jpg",
            "applicantVendors": []
        }
        
        result = parser._extract_food_truck_name(test_item)
        assert result == "Georgia's"
        mock_vision.assert_called_once_with("https://example.com/georgia-logo.jpg")
    
    @pytest.mark.asyncio
    @patch('around_the_grounds.utils.vision_analyzer.VisionAnalyzer.analyze_food_truck_image')
    async def test_fallback_to_tbd_when_vision_fails(self, mock_vision, parser):
        # Mock vision analysis failing
        mock_vision.return_value = None
        
        test_item = {
            "eventTitle": "FOOD TRUCK",
            "eventImage": "https://example.com/unclear.jpg",
            "applicantVendors": []
        }
        
        result = parser._extract_food_truck_name(test_item)
        assert result == "TBD"
```

### 7. Testing with Real Data

Create a test script (`scripts/test_vision_analysis.py`):

```python
#!/usr/bin/env python3
"""Test vision analysis with real Urban Family data."""

import asyncio
import os
from around_the_grounds.utils.vision_analyzer import VisionAnalyzer

async def test_real_image():
    """Test with the actual Georgia's image URL."""
    analyzer = VisionAnalyzer()
    
    test_url = "https://hivey-1.s3.us-east-1.amazonaws.com/uploads/MainlogoB_Webpreview_Georgia's.jpg"
    
    print(f"Analyzing image: {test_url}")
    result = await analyzer.analyze_food_truck_image(test_url)
    
    if result:
        print(f"✅ Vision analysis result: '{result}'")
    else:
        print("❌ Vision analysis failed or returned no result")

if __name__ == "__main__":
    if not os.getenv('ANTHROPIC_API_KEY'):
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        exit(1)
    
    asyncio.run(test_real_image())
```

### 8. Full Application Testing

Run the complete application to test the integration:

```bash
# Set the API key
export ANTHROPIC_API_KEY="your-key-here"

# Test the vision analysis script
uv run python scripts/test_vision_analysis.py

# Run the full application to see vision analysis in action
uv run around-the-grounds --verbose

# Run tests to ensure nothing is broken
uv run python -m pytest tests/unit/test_vision_analyzer.py -v
uv run python -m pytest tests/integration/test_vision_integration.py -v
```

### 9. Performance Considerations

- **Rate Limiting**: Anthropic APIs have rate limits. Implement exponential backoff.
- **Caching**: Cache vision analysis results to avoid re-analyzing the same images.
- **Timeouts**: Set reasonable timeouts for API calls (30 seconds max).
- **Concurrent Limits**: Limit concurrent vision API calls to avoid overwhelming the API.

### 10. Monitoring and Logging

Add detailed logging for vision analysis:

```python
# Enhanced logging in VisionAnalyzer
self.logger.info(f"Vision analysis extracted: '{vendor_name}' from {image_url}")
self.logger.debug(f"Vision API response time: {response_time:.2f}s")
self.logger.warning(f"Vision analysis fallback triggered for {brewery_name}")
```

## Implementation Steps Summary

1. ✅ **Add anthropic dependency** - `uv add anthropic`
2. ✅ **Create VisionAnalyzer class** - New utility module
3. ✅ **Integrate into Urban Family parser** - Modify existing parser
4. ✅ **Add configuration options** - Environment variables and settings
5. ✅ **Implement error handling** - Retry logic and graceful degradation
6. ✅ **Write comprehensive tests** - Unit and integration tests
7. ✅ **Test with real data** - Verify with actual images
8. ✅ **Run full application test** - End-to-end verification

## Expected Outcomes

- Food truck events with clear logos will show actual vendor names instead of "TBD"
- System gracefully falls back to "TBD" when vision analysis fails
- Improved user experience with more informative food truck listings
- Robust error handling ensures the application doesn't break if vision API is unavailable

## Security Considerations

- API key should be stored securely in environment variables
- Validate image URLs before sending to external APIs
- Implement rate limiting to prevent API abuse
- Log API usage for monitoring and cost control