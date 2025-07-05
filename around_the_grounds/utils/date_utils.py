import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging


class DateUtils:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    @staticmethod
    def parse_date_from_text(text: str) -> Optional[datetime]:
        """
        Parse date from various text formats.
        """
        logger = logging.getLogger(__name__)
        
        if not text or len(text.strip()) == 0:
            logger.debug("Empty text provided for date parsing")
            return None
        
        # Common date patterns
        patterns = [
            # MM.DD format
            (r'(\d{1,2})\.(\d{1,2})', lambda m: DateUtils._parse_month_day(int(m.group(1)), int(m.group(2)))),
            # MM/DD/YYYY format
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))),
            # MM-DD-YYYY format
            (r'(\d{1,2})-(\d{1,2})-(\d{4})', lambda m: datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))),
            # Month DD format
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})', 
             lambda m: DateUtils._parse_month_name_day(m.group(1), int(m.group(2)))),
        ]
        
        for pattern, parser in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    result = parser(match)
                    logger.debug(f"Successfully parsed date '{text}' to {result}")
                    return result
                except ValueError as e:
                    logger.debug(f"Failed to parse date with pattern {pattern}: {e}")
                    continue
        
        logger.debug(f"No date pattern matched for text: {text}")
        return None
    
    @staticmethod
    def parse_time_from_text(text: str) -> Optional[Tuple[int, int]]:
        """
        Parse time range from text like "1 — 8pm" or "12:30 - 9:00pm".
        Returns (start_hour, end_hour) in 24-hour format.
        """
        # Pattern for time ranges like "1 — 8pm", "12 - 9pm"
        time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*[—\-]\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)'
        
        match = re.search(time_pattern, text, re.IGNORECASE)
        if match:
            start_hour = int(match.group(1))
            start_min = int(match.group(2)) if match.group(2) else 0
            end_hour = int(match.group(3))
            end_min = int(match.group(4)) if match.group(4) else 0
            period = match.group(5).lower()
            
            # Convert to 24-hour format
            if period == 'pm':
                if start_hour != 12:
                    start_hour += 12
                if end_hour != 12:
                    end_hour += 12
            elif period == 'am':
                if start_hour == 12:
                    start_hour = 0
                if end_hour == 12:
                    end_hour = 0
            
            return (start_hour, end_hour)
        
        return None
    
    @staticmethod
    def _parse_month_day(month: int, day: int) -> datetime:
        """
        Parse month and day, assuming current year or next year if date has passed.
        """
        current_date = datetime.now()
        current_year = current_date.year
        
        # Try current year first
        try:
            date = datetime(current_year, month, day)
            # If date is in the past, try next year
            if date.date() < current_date.date():
                date = datetime(current_year + 1, month, day)
            return date
        except ValueError:
            # Invalid date, try next year
            return datetime(current_year + 1, month, day)
    
    @staticmethod
    def _parse_month_name_day(month_name: str, day: int) -> datetime:
        """
        Parse month name and day.
        """
        month_map = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        month = month_map.get(month_name.lower()[:3])
        if month:
            return DateUtils._parse_month_day(month, day)
        
        raise ValueError(f"Invalid month name: {month_name}")
    
    @staticmethod
    def is_within_next_week(date: datetime) -> bool:
        """
        Check if date is within the next 7 days.
        """
        now = datetime.now()
        one_week_later = now + timedelta(days=7)
        return now.date() <= date.date() <= one_week_later.date()
    
    @staticmethod
    def format_date_for_display(date: datetime) -> str:
        """
        Format date for display in the output.
        """
        return date.strftime("%A, %B %d, %Y")