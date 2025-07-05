import re
from datetime import datetime, timedelta
from typing import List
import aiohttp

from .base import BaseParser
from ..models import FoodTruckEvent


class StoupBallardParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            soup = await self.fetch_page(session, self.brewery.url)
            events = []
            
            if not soup:
                raise ValueError("Failed to fetch page content")
            
            # Find all food truck entries
            food_truck_entries = soup.find_all('div', class_='food-truck-entry')
            
            # If the exact class isn't found, try a more general approach
            if not food_truck_entries:
                # Look for patterns in the HTML structure
                # This is a fallback approach based on common patterns
                for section in soup.find_all('section'):
                    if any(text in section.get_text().lower() for text in ['food truck', 'schedule']):
                        # Extract information from this section
                        entries = self._extract_from_section(section)
                        events.extend(entries)
            else:
                # Process each food truck entry
                for entry in food_truck_entries:
                    event = self._parse_entry(entry)
                    if event:
                        events.append(event)
            
            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events from {len(events)} total")
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing Stoup Ballard: {str(e)}")
            raise ValueError(f"Failed to parse Stoup Ballard website: {str(e)}")
    
    def _extract_from_section(self, section) -> List[FoodTruckEvent]:
        events = []
        text = section.get_text()
        
        # Pattern to match date entries like "Sat 07.05", "Sun 07.06", etc.
        date_pattern = r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(\d{2}\.\d{2})'
        # Pattern to match time ranges like "1 — 8pm", "12 — 9pm"
        time_pattern = r'(\d{1,2})\s*—\s*(\d{1,2})(am|pm)'
        
        lines = text.split('\n')
        current_date = None
        current_time = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for date pattern
            date_match = re.search(date_pattern, line)
            if date_match:
                day_name, date_str = date_match.groups()
                current_date = self._parse_date(date_str)
                continue
            
            # Check for time pattern
            time_match = re.search(time_pattern, line)
            if time_match:
                start_hour, end_hour, period = time_match.groups()
                current_time = (int(start_hour), int(end_hour), period)
                continue
            
            # If we have both date and time, this might be a food truck name
            if current_date and current_time and len(line) > 3:
                # Skip common non-food-truck words
                if not any(word in line.lower() for word in ['schedule', 'food truck', 'ballard']):
                    start_time, end_time = self._parse_time(current_date, current_time)
                    event = FoodTruckEvent(
                        brewery_key=self.brewery.key,
                        brewery_name=self.brewery.name,
                        food_truck_name=line,
                        date=current_date,
                        start_time=start_time,
                        end_time=end_time
                    )
                    events.append(event)
        
        return events
    
    def _parse_entry(self, entry) -> FoodTruckEvent:
        # Extract date
        date_elem = entry.find('h4')
        if not date_elem:
            return None
        
        date_str = date_elem.get_text().strip()
        date = self._parse_date_from_text(date_str)
        
        # Extract time
        time_elem = entry.find('p')
        time_str = time_elem.get_text().strip() if time_elem else ""
        start_time, end_time = self._parse_time_from_text(date, time_str)
        
        # Extract food truck name
        truck_name_elem = entry.find_all('p')
        truck_name = truck_name_elem[-1].get_text().strip() if truck_name_elem else "Unknown"
        
        return FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name=truck_name,
            date=date,
            start_time=start_time,
            end_time=end_time
        )
    
    def _parse_date(self, date_str: str) -> datetime:
        # Parse "07.05" format
        month, day = map(int, date_str.split('.'))
        current_year = datetime.now().year
        
        # Handle year rollover
        current_month = datetime.now().month
        if month < current_month:
            current_year += 1
        
        return datetime(current_year, month, day)
    
    def _parse_date_from_text(self, text: str) -> datetime:
        # Extract date from text like "Sat 07.05"
        date_match = re.search(r'(\d{2}\.\d{2})', text)
        if date_match:
            return self._parse_date(date_match.group(1))
        return datetime.now()
    
    def _parse_time(self, date: datetime, time_tuple: tuple) -> tuple:
        start_hour, end_hour, period = time_tuple
        
        # Convert to 24-hour format
        if period == 'pm' and start_hour != 12:
            start_hour += 12
        elif period == 'am' and start_hour == 12:
            start_hour = 0
        
        if period == 'pm' and end_hour != 12:
            end_hour += 12
        elif period == 'am' and end_hour == 12:
            end_hour = 0
        
        start_time = date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end_time = date.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        
        return start_time, end_time
    
    def _parse_time_from_text(self, date: datetime, time_str: str) -> tuple:
        # Parse time from text like "1 — 8pm"
        time_match = re.search(r'(\d{1,2})\s*—\s*(\d{1,2})(am|pm)', time_str)
        if time_match:
            start_hour, end_hour, period = time_match.groups()
            return self._parse_time(date, (int(start_hour), int(end_hour), period))
        return None, None