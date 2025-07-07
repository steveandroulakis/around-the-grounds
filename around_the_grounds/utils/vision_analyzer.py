import asyncio
import logging
from typing import Optional

import anthropic


class VisionAnalyzer:
    """Analyzes food truck images to extract vendor names using Claude Vision API."""

    def __init__(self, api_key: Optional[str] = None):
        self.client = anthropic.Anthropic(
            api_key=api_key
        )  # Uses ANTHROPIC_API_KEY env var if None
        self.logger = logging.getLogger(__name__)

    async def analyze_food_truck_image(
        self, image_url: str, max_retries: int = 2
    ) -> Optional[str]:
        """
        Analyze a food truck image URL and extract the vendor name with retry logic.

        Args:
            image_url: URL to the food truck image
            max_retries: Maximum number of retry attempts

        Returns:
            Extracted vendor name or None if analysis fails
        """
        # Check if image URL is valid and accessible
        if not self._is_valid_image_url(image_url):
            self.logger.debug(f"Invalid or inaccessible image URL: {image_url}")
            return None

        # Retry logic for network issues
        for attempt in range(max_retries + 1):
            try:
                vendor_name = await self._analyze_image_by_url(image_url)

                if vendor_name:
                    self.logger.info(
                        f"Extracted vendor name from image: '{vendor_name}'"
                    )
                    return vendor_name
                else:
                    self.logger.debug(
                        f"Could not extract vendor name from image: {image_url}"
                    )
                    return None

            except anthropic.APITimeoutError:
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)  # Exponential backoff
                    continue
                self.logger.warning(
                    f"Vision analysis timed out after {max_retries} retries"
                )
            except anthropic.APIError as e:
                self.logger.error(f"Anthropic API error: {str(e)}")
                break
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
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
                                Extract ONLY the business name (e.g., "Georgia's Greek", "Marination", "Paseo", "Whateke"). 
                                Do not include words like "Food Truck", "Kitchen", "Catering" unless they're part of the actual business name.
                                If you cannot clearly identify a business name, respond with "UNKNOWN".
                                Respond with just the business name, nothing else.""",
                            },
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
        if not url or not url.startswith(("http://", "https://")):
            return False

        # Check for common image extensions or image hosting domains
        image_indicators = [
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            "s3.amazonaws.com",
            "images.",
            "img.",
            "media.",
        ]

        url_lower = url.lower()
        return any(indicator in url_lower for indicator in image_indicators)

    def _clean_vendor_name(self, name: str) -> str:
        """Clean extracted vendor name to remove common suffixes."""
        name = name.strip()

        # Remove common business suffixes that Claude might include
        suffixes_to_remove = [
            "Food Truck",
            "Kitchen",
            "Catering",
            "Restaurant",
            "Cafe",
            "Bar",
            "LLC",
            "Inc",
            "Co",
            "Company",
            "&amp;",
            "and Co",
        ]

        for suffix in suffixes_to_remove:
            if name.endswith(suffix):
                name = name[: -len(suffix)].strip()

        return name
