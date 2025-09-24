import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from ..models import Brewery, FoodTruckEvent
from ..utils.date_utils import DateUtils
from ..utils.timezone_utils import PACIFIC_TZ
from ..utils.vision_analyzer import VisionAnalyzer
from ..base import BaseParser


class HiveyApiParser(BaseParser):
    """
    Parser for Hivey calendar platform API endpoints.
    Uses direct JSON API access instead of HTML scraping.
    Can be used by any site that uses Hivey for calendar management.
    """

    def __init__(self, brewery: Brewery) -> None:
        super().__init__(brewery)
        self._vision_analyzer: Optional[VisionAnalyzer] = None
        self._vision_cache: Dict[
            str, Optional[str]
        ] = {}  # Cache for image URL -> vendor name mappings

    @property
    def vision_analyzer(self) -> VisionAnalyzer:
        """Lazy initialization of vision analyzer."""
        if self._vision_analyzer is None:
            self._vision_analyzer = VisionAnalyzer()
        return self._vision_analyzer

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            # Use the API endpoint instead of the public calendar page
            api_url = "https://hivey-api-prod-pineapple.onrender.com/urbanfamily/public-calendar"

            # Required headers to authenticate with the API
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en,en-US;q=0.9,fr;q=0.8,vi;q=0.7,th;q=0.6",
                "origin": "https://app.hivey.io",
                "referer": "https://app.hivey.io/",
                "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
            }

            self.logger.debug(f"Fetching API data from: {api_url}")

            async with session.get(api_url, headers=headers) as response:
                if response.status == 404:
                    raise ValueError(f"API endpoint not found (404): {api_url}")
                elif response.status == 403:
                    raise ValueError(f"Access forbidden (403): {api_url}")
                elif response.status == 500:
                    raise ValueError(f"Server error (500): {api_url}")
                elif response.status != 200:
                    raise ValueError(f"HTTP {response.status}: {api_url}")

                # Parse JSON response
                try:
                    data = await response.json()
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON response from API: {str(e)}")

                if not data:
                    self.logger.info("Empty response from API - no events found")
                    return []

                self.logger.debug(
                    f"Received JSON data with {len(data) if isinstance(data, list) else 'unknown'} items"
                )

                # Parse events from JSON data
                events = self._parse_json_data(data)

                # Filter and validate events
                valid_events = self.filter_valid_events(events)
                self.logger.info(
                    f"Parsed {len(valid_events)} valid events from {len(events)} total"
                )
                return valid_events

        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching Urban Family API: {str(e)}")
        except Exception as e:
            self.logger.error(f"Error parsing Urban Family: {str(e)}")
            if isinstance(e, ValueError):
                raise  # Re-raise our custom ValueError messages
            raise ValueError(f"Failed to parse Urban Family API: {str(e)}")

    def _parse_json_data(self, data: Any) -> List[FoodTruckEvent]:
        """
        Parse JSON data from the Urban Family API into FoodTruckEvent objects.
        """
        events = []

        try:
            # Handle different possible JSON structures
            if isinstance(data, list):
                # If data is a list of events
                for item in data:
                    event = self._parse_event_item(item)
                    if event:
                        events.append(event)
            elif isinstance(data, dict):
                # If data is a dict, look for events in common keys
                if "events" in data:
                    for item in data["events"]:
                        event = self._parse_event_item(item)
                        if event:
                            events.append(event)
                elif "data" in data:
                    for item in data["data"]:
                        event = self._parse_event_item(item)
                        if event:
                            events.append(event)
                else:
                    # Try to parse the entire dict as a single event
                    event = self._parse_event_item(data)
                    if event:
                        events.append(event)
            else:
                self.logger.warning(f"Unexpected data type: {type(data)}")

        except Exception as e:
            self.logger.error(f"Error parsing JSON data: {str(e)}")
            raise ValueError(f"Failed to parse event data: {str(e)}")

        return events

    def _parse_event_item(self, item: Dict[str, Any]) -> Optional[FoodTruckEvent]:
        """
        Parse a single event item from the JSON data.
        """
        try:
            # Extract food truck name from various possible fields
            food_truck_name, ai_generated = self._extract_food_truck_name(item)
            if not food_truck_name:
                # For Urban Family, many events don't have specific vendor names yet
                # Return "TBD" instead of skipping to show the time slot is reserved
                food_truck_name = "TBD"
                ai_generated = False

            # Extract date information
            date = self._extract_date(item)
            if not date:
                self.logger.debug(f"Skipping item without valid date: {item}")
                return None

            # Extract time information
            start_time, end_time = self._extract_times(item, date)

            # Extract description if available
            description = self._extract_description(item)

            return FoodTruckEvent(
                brewery_key=self.brewery.key,
                brewery_name=self.brewery.name,
                food_truck_name=food_truck_name,
                date=date,
                start_time=start_time,
                end_time=end_time,
                description=description,
                ai_generated_name=ai_generated,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing event item: {str(e)}, item: {item}")
            return None

    def _extract_food_truck_name(
        self, item: Dict[str, Any]
    ) -> Tuple[Optional[str], bool]:
        """
        Extract food truck name with vision analysis fallback.
        Returns a tuple of (extracted_name, ai_generated) where:
        - extracted_name: The vendor name or None if no valid name found
        - ai_generated: True if name was extracted using AI vision analysis
        """
        # Try existing text-based extraction methods first
        name = self._extract_name_from_text_fields(item)
        if name:
            return name, False

        # If no name found from text, try image analysis
        if "eventImage" in item and item["eventImage"]:
            image_url = str(item["eventImage"])

            # Check cache first
            if image_url in self._vision_cache:
                cached_name = self._vision_cache[image_url]
                if cached_name:
                    self.logger.debug(
                        f"Using cached vision result for {image_url}: {cached_name}"
                    )
                    return cached_name, True
                else:
                    self.logger.debug(
                        f"Cached vision result for {image_url} was None, retrying vision analysis"
                    )
                    # Don't return early - retry vision analysis for failed cache entries
                    # This helps recover from temporary failures

            self.logger.debug(f"Attempting vision analysis for image: {image_url}")

            # Use asyncio to run the async vision analysis
            try:
                # Try to get the running event loop first
                try:
                    asyncio.get_running_loop()
                    # If there's already a running loop, we need to use a different approach
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.vision_analyzer.analyze_food_truck_image(image_url),
                        )
                        vision_name = future.result(timeout=30)
                except RuntimeError:
                    # No running event loop, safe to create a new one
                    vision_name = asyncio.run(
                        self.vision_analyzer.analyze_food_truck_image(image_url)
                    )

                # Cache the result (even if None)
                self._vision_cache[image_url] = vision_name

                if vision_name:
                    self.logger.info(
                        f"Vision analysis extracted name: {vision_name} from {image_url}"
                    )
                    return vision_name, True
                else:
                    self.logger.warning(
                        f"Vision analysis returned no name for {image_url}"
                    )
            except Exception as e:
                self.logger.warning(f"Vision analysis failed for {image_url}: {str(e)}")
                # Don't cache failures permanently - allow retries on subsequent runs
                # Only cache successful results or after multiple failures

        # Return None if no valid name found
        return None, False

    def _extract_name_from_text_fields(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract name from text fields (existing logic moved here)."""
        # Try eventTitle first - some have food truck names
        if "eventTitle" in item and item["eventTitle"]:
            title = str(item["eventTitle"]).strip()
            # If the title contains "FOOD TRUCK - " followed by a name, extract it
            if "FOOD TRUCK - " in title:
                name = title.replace("FOOD TRUCK - ", "").strip()
                if name and name.lower() not in [
                    "tbd",
                    "tba",
                    "to be announced",
                    "unknown",
                ]:
                    return name
            # If it's not just "FOOD TRUCK", use the title
            elif title.lower() != "food truck":
                return title

        # Try to get vendor information from applicantVendors
        if "applicantVendors" in item and item["applicantVendors"]:
            vendors = item["applicantVendors"]
            if isinstance(vendors, list) and len(vendors) > 0:
                vendor = vendors[0]  # Take the first vendor
                if isinstance(vendor, dict) and "vendorId" in vendor:
                    vendor_id = vendor["vendorId"]
                    # Try vendor ID mapping first
                    mapped_name = self._get_vendor_name_by_id(vendor_id)
                    if mapped_name:
                        self.logger.debug(
                            f"Mapped vendor ID {vendor_id} to {mapped_name}"
                        )
                        return mapped_name

        # Try other common field names
        possible_names = [
            "name",
            "vendor",
            "vendor_name",
            "food_truck",
            "food_truck_name",
            "truck_name",
            "business_name",
            "summary",
        ]

        for field in possible_names:
            if field in item and item[field]:
                name = str(item[field]).strip()
                if name and name.lower() not in [
                    "tbd",
                    "tba",
                    "to be announced",
                    "unknown",
                    "food truck",
                ]:
                    return name

        # Try to extract from eventImage filename as a fallback, but be very selective
        if "eventImage" in item and item["eventImage"]:
            image_url = str(item["eventImage"])
            # Extract filename from URL
            import os

            filename = os.path.basename(image_url)
            # Remove extension and clean up
            name = os.path.splitext(filename)[0]
            # Clean up the name (remove underscores, etc.)
            name = name.replace("_", " ").replace("-", " ").strip()

            # Smart filename parsing for Urban Family patterns
            # Handle patterns like "LOGO_momo.png" -> "momo"
            # Handle patterns like "MainlogoB_Webpreview_Georgia's.jpg" -> "Georgia's"

            # First, try to extract meaningful parts from compound filenames
            vendor_name = self._extract_vendor_from_filename(name)
            if vendor_name:
                self.logger.debug(f"Extracted vendor name from filename: {vendor_name}")
                return vendor_name

        return None

    def _get_vendor_name_by_id(self, vendor_id: str) -> Optional[str]:
        """
        Map vendor IDs to known vendor names based on observed patterns.
        This is a fallback when API vendor lookup isn't available.
        """
        # Known vendor ID mappings from Urban Family calendar data
        vendor_mappings = {
            "67f07a79e9f3be17e2ef63b5": "MomoExpress",  # LOGO_momo.png
            "67f6f627e4ca31e444ef637e": "Kaosamai Thai Restaurant",  # kaosamia.png
            "67f6f6bde4ca31e444ef637f": "Georgia's Greek",  # MainlogoB_Webpreview_Georgia's.jpg
            "67f064f0e9f3be17e2ef63b0": "Impeckable Chicken",  # Common recurring vendor
            "67f074a2e9f3be17e2ef63b1": "Tacos & Beer",  # From debug logs
            "67f077c5e9f3be17e2ef63b4": "Oskar's Pizza",  # From debug logs
            "67f081a5e9f3be17e2ef63b8": "Burger Planet",  # From debug logs
            "67f0ab6de9f3be17e2ef63bd": "Kathmandu momoCha",  # From debug logs
            "67f6f76ce4ca31e444ef6380": "Alebrije",  # From debug logs
            "67f5a888e9f3be17e2ef63ce": "Birrieria Pepe El Toro LLC",  # From debug logs
            # Add more mappings as they're discovered
        }

        mapped_name = vendor_mappings.get(vendor_id)
        if mapped_name:
            return mapped_name

        # If no mapping found, log the vendor ID for future mapping
        self.logger.debug(
            f"Unknown vendor ID: {vendor_id} - consider adding to mappings"
        )
        return None

    def _extract_vendor_from_filename(self, filename: str) -> Optional[str]:
        """
        Extract vendor name from filename using Urban Family specific patterns.
        """
        import re

        # Clean up the filename
        name = filename.replace("_", " ").replace("-", " ").strip()

        # Pattern 1: "LOGO momo" -> "momo"
        logo_match = re.search(
            r"(?:logo|LOGO)\s+([a-zA-Z][a-zA-Z0-9\s\']*)", name, re.IGNORECASE
        )
        if logo_match:
            extracted = logo_match.group(1).strip()
            if len(extracted) > 1:
                return extracted.title()

        # Pattern 2: "MainlogoB Webpreview Georgia's" -> "Georgia's"
        # Look for known food truck name patterns at the end
        food_indicators = r"(\b(?:[A-Z][a-z]+\'?s?\s*)+)$"
        food_match = re.search(food_indicators, name)
        if food_match:
            extracted = food_match.group(1).strip()
            # Validate it's not just metadata
            if not any(
                word.lower() in ["logo", "main", "web", "preview", "header"]
                for word in extracted.split()
            ):
                return extracted

        # Pattern 3: Simple case - just clean filename if it looks like a vendor name
        # Remove common prefixes and suffixes
        cleaned = re.sub(
            r"^(logo|main|web|header|image)\s*", "", name, flags=re.IGNORECASE
        )
        cleaned = re.sub(
            r"\s*(logo|web|preview|header|image|main)$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip()

        # If what's left looks like a business name (letters, maybe spaces/apostrophes)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9\s\']+$", cleaned) and len(cleaned) > 2:
            # Exclude obvious metadata terms
            excluded_terms = [
                "blk",
                "black",
                "white",
                "temp",
                "tmp",
                "default",
                "unnamed",
                "placeholder",
                "copy",
                "screen",
                "shot",
                "updated",
            ]
            if not any(term in cleaned.lower() for term in excluded_terms):
                return cleaned.title()

        return None

    def _extract_date(self, item: Dict[str, Any]) -> Optional[datetime]:
        """
        Extract date from various possible fields and formats.
        """
        # For Urban Family, dates are in eventDates array
        if "eventDates" in item and item["eventDates"]:
            event_dates = item["eventDates"]
            if isinstance(event_dates, list) and len(event_dates) > 0:
                event_date = event_dates[0]  # Take the first date
                if isinstance(event_date, dict) and "date" in event_date:
                    date_str = event_date["date"]
                    parsed_date = self._parse_urban_family_date(date_str)
                    if parsed_date:
                        return parsed_date

        # Common field names for dates (fallback)
        possible_dates = [
            "date",
            "start_date",
            "event_date",
            "start",
            "start_time",
            "datetime",
            "created_at",
            "scheduled_date",
        ]

        for field in possible_dates:
            if field in item and item[field]:
                date_str = str(item[field])
                parsed_date = DateUtils.parse_date_from_text(date_str)
                if parsed_date:
                    return parsed_date

        return None

    def _parse_urban_family_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse Urban Family date format like "July 06, 2025".
        """
        try:
            # Parse "July 06, 2025" format
            return datetime.strptime(date_str, "%B %d, %Y")
        except ValueError:
            # Try other common formats
            try:
                return datetime.strptime(date_str, "%B %d %Y")
            except ValueError:
                try:
                    return datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    # Fall back to the utility function
                    return DateUtils.parse_date_from_text(date_str)

    def _extract_times(self, item: Dict[str, Any], date: datetime) -> tuple:
        """
        Extract start and end times from the event data.
        """
        start_time = None
        end_time = None

        # For Urban Family, times are in eventDates array
        if "eventDates" in item and item["eventDates"]:
            event_dates = item["eventDates"]
            if isinstance(event_dates, list) and len(event_dates) > 0:
                event_date = event_dates[0]  # Take the first date
                if isinstance(event_date, dict):
                    if "startTime" in event_date:
                        start_time = self._parse_time_string(
                            event_date["startTime"], date
                        )
                    if "endTime" in event_date:
                        end_time = self._parse_time_string(event_date["endTime"], date)

        # Fallback: Look for time information in various fields
        if not start_time and not end_time:
            time_fields = [
                "start_time",
                "end_time",
                "time",
                "duration",
                "start",
                "end",
                "scheduled_time",
            ]

            for field in time_fields:
                if field in item and item[field]:
                    time_str = str(item[field])

                    if "start" in field.lower():
                        start_time = self._parse_time_string(time_str, date)
                    elif "end" in field.lower():
                        end_time = self._parse_time_string(time_str, date)
                    elif field == "time":
                        # Try to parse as a time range
                        parsed_times = self._parse_time_range(time_str, date)
                        if parsed_times:
                            start_time, end_time = parsed_times

        return start_time, end_time

    def _extract_description(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Extract description from various possible fields.
        """
        possible_descriptions = ["description", "details", "notes", "content", "body"]

        for field in possible_descriptions:
            if field in item and item[field]:
                desc = str(item[field]).strip()
                if desc:
                    return desc

        return None

    def _parse_time_string(self, time_str: str, date: datetime) -> Optional[datetime]:
        """
        Parse a time string and combine with the given date.
        """
        try:
            # Handle ISO format timestamps
            if "T" in time_str or "+" in time_str:
                # Parse ISO format and convert to Pacific timezone
                iso_dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if iso_dt.tzinfo is not None:
                    # Convert to Pacific timezone and make naive
                    pacific_dt = iso_dt.astimezone(PACIFIC_TZ)
                    return pacific_dt.replace(tzinfo=None)
                return iso_dt

            # Handle Urban Family time format like "13:00", "19:00"
            import re

            # 24-hour format (HH:MM) - assume Pacific timezone
            time_match = re.search(r"^(\d{1,2}):(\d{2})$", time_str.strip())
            if time_match:
                hour, minute = map(int, time_match.groups())

                # Validate hour and minute
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    # Create timezone-naive Pacific time
                    return date.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )

            # Handle 12-hour format with AM/PM
            time_match = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str.lower())
            if time_match:
                hour_str, minute_str, period = time_match.groups()
                hour = int(hour_str)
                minute = int(minute_str)

                # Convert to 24-hour format
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0

                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    # Create timezone-naive Pacific time
                    return date.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )

        except Exception as e:
            self.logger.debug(f"Error parsing time string '{time_str}': {str(e)}")

        return None

    def _parse_time_range(self, time_str: str, date: datetime) -> tuple:
        """
        Parse a time range string like "2:00 PM - 6:00 PM".
        """
        try:
            import re

            # Look for time range patterns
            range_match = re.search(
                r"(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–—]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)",
                time_str,
                re.IGNORECASE,
            )
            if range_match:
                start_str, end_str = range_match.groups()
                start_time = self._parse_time_string(start_str, date)
                end_time = self._parse_time_string(end_str, date)
                return start_time, end_time

        except Exception as e:
            self.logger.debug(f"Error parsing time range '{time_str}': {str(e)}")

        return None, None
