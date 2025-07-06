import re
from datetime import datetime, timedelta
from typing import List
import aiohttp
import json

from .base import BaseParser
from ..models import FoodTruckEvent


class BaleBreakerParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            # First, get the main page to find the collection ID
            soup = await self.fetch_page(session, self.brewery.url)
            if not soup:
                raise ValueError("Failed to fetch page content")
            
            # Extract collection ID from the calendar block
            collection_id = self._extract_collection_id(soup)
            if not collection_id:
                self.logger.warning("Could not find collection ID, falling back to placeholder event")
                return self._create_fallback_event()
            
            # Fetch calendar events from API
            events = await self._fetch_calendar_events(session, collection_id)
            
            # If no events found, fall back to placeholder
            if not events:
                self.logger.warning("No events found from API, falling back to placeholder event")
                return self._create_fallback_event()
            
            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events from {len(events)} total")
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing Bale Breaker: {str(e)}")
            # Return fallback event instead of failing completely
            return self._create_fallback_event()
    
    def _extract_collection_id(self, soup) -> str:
        """Extract the Squarespace calendar collection ID from the page"""
        try:
            # Look for calendar block with data-block-json attribute
            calendar_blocks = soup.find_all('div', {'class': 'calendar-block'})
            for block in calendar_blocks:
                data_json = block.get('data-block-json')
                if data_json:
                    # Decode HTML entities and parse JSON
                    import html
                    decoded_json = html.unescape(data_json)
                    block_data = json.loads(decoded_json)
                    collection_id = block_data.get('collectionId')
                    if collection_id:
                        self.logger.debug(f"Found collection ID: {collection_id}")
                        return collection_id
            
            # Fallback: look in script tags for collection info
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'collectionId' in script.string:
                    text = script.string
                    import re
                    match = re.search(r'"collectionId":"([^"]+)"', text)
                    if match:
                        collection_id = match.group(1)
                        self.logger.debug(f"Found collection ID in script: {collection_id}")
                        return collection_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting collection ID: {str(e)}")
            return None
    
    async def _fetch_calendar_events(self, session: aiohttp.ClientSession, collection_id: str) -> List[FoodTruckEvent]:
        """Fetch events from the Squarespace calendar API"""
        events = []
        
        try:
            # Get current month and next few months
            now = datetime.now()
            months_to_fetch = [
                (now.year, now.month),
                ((now + timedelta(days=32)).year, (now + timedelta(days=32)).month),
                ((now + timedelta(days=63)).year, (now + timedelta(days=63)).month)
            ]
            
            for year, month in months_to_fetch:
                month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                              'July', 'August', 'September', 'October', 'November', 'December']
                month_str = f"{month_names[month-1]}-{year}"  # MMMM-yyyy format
                api_url = f"https://www.bbycballard.com/api/open/GetItemsByMonth?month={month_str}&collectionId={collection_id}"
                
                self.logger.debug(f"Fetching calendar data from: {api_url}")
                
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.logger.debug(f"Found {len(data)} events for {month_str}")
                        
                        for event_data in data:
                            event = self._parse_api_event(event_data)
                            if event:
                                events.append(event)
                    else:
                        self.logger.warning(f"API request failed with status {response.status}")
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error fetching calendar events: {str(e)}")
            return []
    
    def _parse_api_event(self, event_data: dict) -> FoodTruckEvent:
        """Parse a single event from the Squarespace API response"""
        try:
            title = event_data.get('title', '').strip()
            if not title:
                return None
            
            # Convert timestamp to datetime
            start_timestamp = event_data.get('startDate')
            end_timestamp = event_data.get('endDate')
            
            if not start_timestamp:
                return None
            
            # Squarespace timestamps are in milliseconds
            start_date = datetime.fromtimestamp(start_timestamp / 1000)
            end_date = None
            if end_timestamp:
                end_date = datetime.fromtimestamp(end_timestamp / 1000)
            
            # Create event
            event = FoodTruckEvent(
                brewery_key=self.brewery.key,
                brewery_name=self.brewery.name,
                food_truck_name=title,
                date=start_date,
                end_time=end_date,
                description=None  # Don't show generic description to users
            )
            
            self.logger.debug(f"Parsed event: {title} on {start_date}")
            return event
            
        except Exception as e:
            self.logger.error(f"Error parsing API event: {str(e)}")
            return None
    
    def _create_fallback_event(self) -> List[FoodTruckEvent]:
        """Create a fallback event when API parsing fails"""
        placeholder_event = FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name="Check Instagram @BaleBreaker",
            date=datetime.now(),
            description="Food truck schedule not available - check Instagram or website directly"
        )
        return [placeholder_event]