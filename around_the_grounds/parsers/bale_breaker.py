import re
from datetime import datetime, timedelta
from typing import List
import aiohttp

from .base import BaseParser
from ..models import FoodTruckEvent


class BaleBreakerParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            soup = await self.fetch_page(session, self.brewery.url)
            events = []
            
            if not soup:
                raise ValueError("Failed to fetch page content")
            
            # Look for any event or calendar sections
            event_sections = soup.find_all(['div', 'section'], class_=re.compile(r'event|calendar|schedule'))
            
            for section in event_sections:
                events.extend(self._extract_events_from_section(section))
            
            # If no structured events found, look for text patterns
            if not events:
                events = self._extract_from_text(soup.get_text())
            
            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(f"Parsed {len(valid_events)} valid events from {len(events)} total")
            return valid_events
            
        except Exception as e:
            self.logger.error(f"Error parsing Bale Breaker: {str(e)}")
            raise ValueError(f"Failed to parse Bale Breaker website: {str(e)}")
    
    def _extract_events_from_section(self, section) -> List[FoodTruckEvent]:
        events = []
        text = section.get_text()
        
        # Look for common date patterns
        date_patterns = [
            r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun).*?(\d{1,2}[/.-]\d{1,2})',
            r'(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec).*?(\d{1,2})'
        ]
        
        # Look for food truck names or event descriptions
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip common non-event text
            if any(word in line.lower() for word in ['contact', 'hours', 'location', 'instagram']):
                continue
            
            # Look for potential food truck names or events
            if any(word in line.lower() for word in ['food truck', 'truck', 'kitchen', 'bbq', 'taco', 'burger']):
                # Try to extract date from nearby text
                event = self._create_event_from_text(line)
                if event:
                    events.append(event)
        
        return events
    
    def _extract_from_text(self, text: str) -> List[FoodTruckEvent]:
        events = []
        
        # Since the site doesn't have structured data, we'll create a placeholder
        # that indicates manual checking is needed
        placeholder_event = FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name="Check Instagram @BaleBreaker",
            date=datetime.now(),
            description="Food truck schedule not available on website - check Instagram"
        )
        events.append(placeholder_event)
        
        return events
    
    def _create_event_from_text(self, text: str) -> FoodTruckEvent:
        # Extract potential food truck name
        food_truck_name = text.strip()
        
        # Create event with today's date as placeholder
        return FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name=food_truck_name,
            date=datetime.now(),
            description=f"Extracted from: {text}"
        )
    
    def _parse_date(self, date_str: str) -> datetime:
        # Try different date formats
        formats = [
            '%m/%d/%Y',
            '%m-%d-%Y',
            '%m.%d.%Y',
            '%m/%d',
            '%m-%d'
        ]
        
        for fmt in formats:
            try:
                date = datetime.strptime(date_str, fmt)
                # If year not specified, assume current year
                if date.year == 1900:
                    date = date.replace(year=datetime.now().year)
                return date
            except ValueError:
                continue
        
        # If no format matches, return current date
        return datetime.now()