import re
from datetime import datetime
from typing import List
import aiohttp

from .base import BaseParser
from ..models import FoodTruckEvent


class ObecBrewingParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            soup = await self.fetch_page(session, self.brewery.url)
            events = []
            
            if not soup:
                raise ValueError("Failed to fetch page content")
            
            # Get all text content from the page
            page_text = soup.get_text()
            
            # Use the regex pattern from config to find food truck information
            # Pattern: "Food truck:\s*([^0-9]+)\s*([0-9:]+\s*-\s*[0-9:]+)"
            pattern = self.brewery.parser_config.get('pattern', r'Food truck:\s*([^0-9]+)\s*([0-9:]+\s*-\s*[0-9:]+)')
            
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                truck_name = match.group(1).strip()
                time_range = match.group(2).strip()
                
                # Parse the time range (e.g., "4:00 - 8:00")
                start_time, end_time = self._parse_time_range(time_range)
                
                # Create event for today
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                
                event = FoodTruckEvent(
                    brewery_key=self.brewery.key,
                    brewery_name=self.brewery.name,
                    food_truck_name=truck_name,
                    date=today,
                    start_time=start_time,
                    end_time=end_time,
                    ai_generated_name=False
                )
                events.append(event)
            
            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events from {len(events)} total")
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing Obec Brewing: {str(e)}")
            raise ValueError(f"Failed to parse Obec Brewing website: {str(e)}")
    
    def _parse_time_range(self, time_range: str) -> tuple:
        """Parse time range like '4:00 - 8:00' into start and end datetime objects."""
        try:
            # Split on dash/hyphen
            time_parts = re.split(r'\s*[-–—]\s*', time_range)
            if len(time_parts) != 2:
                return None, None
            
            start_str, end_str = time_parts
            
            # Parse individual times
            start_time = self._parse_single_time(start_str.strip())
            end_time = self._parse_single_time(end_str.strip())
            
            if start_time and end_time:
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                start_datetime = today.replace(hour=start_time[0], minute=start_time[1])
                end_datetime = today.replace(hour=end_time[0], minute=end_time[1])
                return start_datetime, end_datetime
            
            return None, None
            
        except Exception as e:
            self.logger.warning(f"Failed to parse time range '{time_range}': {str(e)}")
            return None, None
    
    def _parse_single_time(self, time_str: str) -> tuple:
        """Parse a single time like '4:00' or '16:00' into (hour, minute)."""
        try:
            # Handle formats like "4:00", "16:00", "4", etc.
            time_match = re.match(r'(\d{1,2})(?::(\d{2}))?', time_str)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0
                
                # For food truck hours, assume PM for reasonable hours (4-11)
                # Only treat as 24-hour format if hour > 12
                if hour > 12:
                    # Already in 24-hour format, use as-is
                    pass
                elif hour >= 4 and hour <= 11:
                    hour += 12  # Convert 4-11 to PM (16-23)
                elif hour == 12:
                    hour = 12  # Keep 12 as noon
                # Hours 1-3 stay as AM (1-3)
                
                # Validate hour range
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return (hour, minute)
            
            return None
            
        except Exception:
            return None