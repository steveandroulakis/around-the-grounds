import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import aiohttp

from .base import BaseParser
from ..models import FoodTruckEvent
from ..utils.date_utils import DateUtils
from ..utils.vision_analyzer import VisionAnalyzer


class UrbanFamilyParser(BaseParser):
    """
    Parser for Urban Family Brewing using their API endpoint.
    Uses direct JSON API access instead of HTML scraping.
    """
    
    def __init__(self, brewery):
        super().__init__(brewery)
        self._vision_analyzer = None
        self._vision_cache = {}  # Cache for image URL -> vendor name mappings
    
    @property
    def vision_analyzer(self):
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
                'accept': 'application/json, text/plain, */*',
                'accept-language': 'en,en-US;q=0.9,fr;q=0.8,vi;q=0.7,th;q=0.6',
                'origin': 'https://app.hivey.io',
                'referer': 'https://app.hivey.io/',
                'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
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
                
                self.logger.debug(f"Received JSON data with {len(data) if isinstance(data, list) else 'unknown'} items")
                
                # Parse events from JSON data
                events = self._parse_json_data(data)
                
                # Filter and validate events
                valid_events = self.filter_valid_events(events)
                self.logger.info(f"Parsed {len(valid_events)} valid events from {len(events)} total")
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
                if 'events' in data:
                    for item in data['events']:
                        event = self._parse_event_item(item)
                        if event:
                            events.append(event)
                elif 'data' in data:
                    for item in data['data']:
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
    
    def _parse_event_item(self, item: Dict[str, Any]) -> FoodTruckEvent:
        """
        Parse a single event item from the JSON data.
        """
        try:
            # Extract food truck name from various possible fields
            food_truck_name = self._extract_food_truck_name(item)
            if not food_truck_name:
                # For Urban Family, many events don't have specific vendor names yet
                # Return "TBD" instead of skipping to show the time slot is reserved
                food_truck_name = "TBD"
            
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
                description=description
            )
            
        except Exception as e:
            self.logger.debug(f"Error parsing event item: {str(e)}, item: {item}")
            return None
    
    def _extract_food_truck_name(self, item: Dict[str, Any]) -> Optional[str]:
        """
        Extract food truck name with vision analysis fallback.
        Returns the extracted name or None if no valid name can be determined.
        """
        # Try existing text-based extraction methods first
        name = self._extract_name_from_text_fields(item)
        if name:
            return name
        
        # If no name found from text, try image analysis
        if 'eventImage' in item and item['eventImage']:
            image_url = str(item['eventImage'])
            
            # Check cache first
            if image_url in self._vision_cache:
                cached_name = self._vision_cache[image_url]
                if cached_name:
                    self.logger.debug(f"Using cached vision result for {image_url}: {cached_name}")
                    return cached_name
                else:
                    self.logger.debug(f"Cached vision result for {image_url} was None, skipping")
                    return None
            
            self.logger.debug(f"Attempting vision analysis for image: {image_url}")
            
            # Use asyncio to run the async vision analysis
            try:
                # Try to get the running event loop first
                try:
                    loop = asyncio.get_running_loop()
                    # If there's already a running loop, we need to use a different approach
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.vision_analyzer.analyze_food_truck_image(image_url)
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
                    self.logger.info(f"Vision analysis extracted name: {vision_name}")
                    return vision_name
            except Exception as e:
                self.logger.debug(f"Vision analysis failed: {str(e)}")
                # Cache the failure
                self._vision_cache[image_url] = None
        
        # Return None if no valid name found
        return None
    
    def _extract_name_from_text_fields(self, item: Dict[str, Any]) -> Optional[str]:
        """Extract name from text fields (existing logic moved here)."""
        # Try eventTitle first - some have food truck names
        if 'eventTitle' in item and item['eventTitle']:
            title = str(item['eventTitle']).strip()
            # If the title contains "FOOD TRUCK - " followed by a name, extract it
            if 'FOOD TRUCK - ' in title:
                name = title.replace('FOOD TRUCK - ', '').strip()
                if name and name.lower() not in ['tbd', 'tba', 'to be announced', 'unknown']:
                    return name
            # If it's not just "FOOD TRUCK", use the title
            elif title.lower() != 'food truck':
                return title
        
        # Try to get vendor information from applicantVendors
        if 'applicantVendors' in item and item['applicantVendors']:
            vendors = item['applicantVendors']
            if isinstance(vendors, list) and len(vendors) > 0:
                vendor = vendors[0]  # Take the first vendor
                if isinstance(vendor, dict) and 'vendorId' in vendor:
                    # For now, we'll need to make an additional API call to get vendor details
                    # But let's try to extract from other fields first
                    pass
        
        # Try other common field names
        possible_names = [
            'name', 'vendor', 'vendor_name', 'food_truck', 
            'food_truck_name', 'truck_name', 'business_name', 'summary'
        ]
        
        for field in possible_names:
            if field in item and item[field]:
                name = str(item[field]).strip()
                if name and name.lower() not in ['tbd', 'tba', 'to be announced', 'unknown', 'food truck']:
                    return name
        
        # Try to extract from eventImage filename as a fallback, but be very selective
        if 'eventImage' in item and item['eventImage']:
            image_url = str(item['eventImage'])
            # Extract filename from URL
            import os
            filename = os.path.basename(image_url)
            # Remove extension and clean up
            name = os.path.splitext(filename)[0]
            # Clean up the name (remove underscores, etc.)
            name = name.replace('_', ' ').replace('-', ' ').strip()
            
            # Be very selective - exclude generic logo names and metadata
            excluded_terms = [
                'logo', 'image', 'unnamed', 'header', 'updated', 'blk', 'black', 
                'white', 'main', 'screen', 'shot', 'copy', 'preview', 'web',
                'temp', 'tmp', 'placeholder', 'default'
            ]
            
            # Check if the name contains mostly excluded terms
            name_words = name.lower().split()
            if name_words and len(name) > 3:
                excluded_count = sum(1 for word in name_words if any(term in word for term in excluded_terms))
                # If more than half the words are excluded terms, skip this
                if excluded_count <= len(name_words) / 2:
                    # Additional check: ensure it's not just metadata
                    if not any(name.lower().startswith(term) for term in ['logo', 'updated', 'main']):
                        return name.title()
        
        return None
    
    def _extract_date(self, item: Dict[str, Any]) -> datetime:
        """
        Extract date from various possible fields and formats.
        """
        # For Urban Family, dates are in eventDates array
        if 'eventDates' in item and item['eventDates']:
            event_dates = item['eventDates']
            if isinstance(event_dates, list) and len(event_dates) > 0:
                event_date = event_dates[0]  # Take the first date
                if isinstance(event_date, dict) and 'date' in event_date:
                    date_str = event_date['date']
                    parsed_date = self._parse_urban_family_date(date_str)
                    if parsed_date:
                        return parsed_date
        
        # Common field names for dates (fallback)
        possible_dates = [
            'date', 'start_date', 'event_date', 'start', 'start_time',
            'datetime', 'created_at', 'scheduled_date'
        ]
        
        for field in possible_dates:
            if field in item and item[field]:
                date_str = str(item[field])
                parsed_date = DateUtils.parse_date_from_text(date_str)
                if parsed_date:
                    return parsed_date
        
        return None
    
    def _parse_urban_family_date(self, date_str: str) -> datetime:
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
        if 'eventDates' in item and item['eventDates']:
            event_dates = item['eventDates']
            if isinstance(event_dates, list) and len(event_dates) > 0:
                event_date = event_dates[0]  # Take the first date
                if isinstance(event_date, dict):
                    if 'startTime' in event_date:
                        start_time = self._parse_time_string(event_date['startTime'], date)
                    if 'endTime' in event_date:
                        end_time = self._parse_time_string(event_date['endTime'], date)
        
        # Fallback: Look for time information in various fields
        if not start_time and not end_time:
            time_fields = [
                'start_time', 'end_time', 'time', 'duration', 
                'start', 'end', 'scheduled_time'
            ]
            
            for field in time_fields:
                if field in item and item[field]:
                    time_str = str(item[field])
                    
                    if 'start' in field.lower():
                        start_time = self._parse_time_string(time_str, date)
                    elif 'end' in field.lower():
                        end_time = self._parse_time_string(time_str, date)
                    elif field == 'time':
                        # Try to parse as a time range
                        parsed_times = self._parse_time_range(time_str, date)
                        if parsed_times:
                            start_time, end_time = parsed_times
        
        return start_time, end_time
    
    def _extract_description(self, item: Dict[str, Any]) -> str:
        """
        Extract description from various possible fields.
        """
        possible_descriptions = [
            'description', 'details', 'notes', 'content', 'body'
        ]
        
        for field in possible_descriptions:
            if field in item and item[field]:
                desc = str(item[field]).strip()
                if desc:
                    return desc
        
        return None
    
    def _parse_time_string(self, time_str: str, date: datetime) -> datetime:
        """
        Parse a time string and combine with the given date.
        """
        try:
            # Handle ISO format timestamps
            if 'T' in time_str or '+' in time_str:
                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            # Handle Urban Family time format like "13:00", "19:00"
            import re
            
            # 24-hour format (HH:MM)
            time_match = re.search(r'^(\d{1,2}):(\d{2})$', time_str.strip())
            if time_match:
                hour, minute = map(int, time_match.groups())
                
                # Validate hour and minute
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Handle 12-hour format with AM/PM
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)', time_str.lower())
            if time_match:
                hour, minute, period = time_match.groups()
                hour = int(hour)
                minute = int(minute)
                
                # Convert to 24-hour format
                if period == 'pm' and hour != 12:
                    hour += 12
                elif period == 'am' and hour == 12:
                    hour = 0
                
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
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
            range_match = re.search(r'(\d{1,2}:\d{2}(?:\s*[AP]M)?)\s*[-–—]\s*(\d{1,2}:\d{2}(?:\s*[AP]M)?)', time_str, re.IGNORECASE)
            if range_match:
                start_str, end_str = range_match.groups()
                start_time = self._parse_time_string(start_str, date)
                end_time = self._parse_time_string(end_str, date)
                return start_time, end_time
            
        except Exception as e:
            self.logger.debug(f"Error parsing time range '{time_str}': {str(e)}")
        
        return None, None