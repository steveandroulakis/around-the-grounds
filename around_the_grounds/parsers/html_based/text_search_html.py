import re
from datetime import datetime
from typing import List, Optional

import aiohttp

from ..models import FoodTruckEvent
from ..utils.timezone_utils import (
    get_pacific_month,
    get_pacific_year,
    parse_date_with_pacific_context,
)
from ..base import BaseParser


class TextSearchHtmlParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        try:
            soup = await self.fetch_page(session, self.brewery.url)
            events = []

            if not soup:
                raise ValueError("Failed to fetch page content")

            # Look for the "UPCOMING FOOD TRUCKS" section in the HTML
            upcoming_element = soup.find(
                string=lambda text: bool(text and "UPCOMING FOOD TRUCKS" in text)
            )
            if not upcoming_element:
                self.logger.warning("Could not find 'UPCOMING FOOD TRUCKS' section")
                return []

            # Find the parent element containing the schedule
            parent = upcoming_element.parent
            while parent and parent.name not in ["section", "div", "body"]:
                parent = parent.parent

            if not parent:
                self.logger.warning(
                    "Could not find parent container for food truck schedule"
                )
                return []

            # Look for all <p> elements that contain food truck schedule entries
            schedule_paragraphs = parent.find_all("p")

            for p in schedule_paragraphs:
                # Get the text content from the paragraph
                text = p.get_text().strip()
                if not text:
                    continue

                # Skip the header itself
                if "UPCOMING FOOD TRUCKS" in text:
                    continue

                # Try to parse food truck entries
                event = self._parse_food_truck_line(text)
                if event:
                    events.append(event)

            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(
                f"Parsed {len(valid_events)} valid events from {len(events)} total"
            )
            return valid_events

        except Exception as e:
            self.logger.error(f"Error parsing Wheelie Pop: {str(e)}")
            raise ValueError(f"Failed to parse Wheelie Pop website: {str(e)}")

    def _parse_food_truck_line(self, line: str) -> Optional[FoodTruckEvent]:
        """
        Parse a line like "Thursday, 7/3: Tisket Tasket"
        """
        try:
            # Pattern to match: Day, M/D: Food Truck Name (flexible with whitespace)
            pattern = r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,\s*(\d{1,2}/\d{1,2})\s*:\s*(.+)"
            match = re.match(pattern, line.strip())

            if not match:
                self.logger.debug(f"Line doesn't match pattern: {line}")
                return None

            day_name, date_str, truck_name = match.groups()

            # Parse the date (M/D format)
            date = self._parse_date(date_str.strip())
            if not date:
                self.logger.debug(f"Could not parse date: {date_str}")
                return None

            # Clean up the truck name
            truck_name = truck_name.strip()
            if not truck_name:
                self.logger.debug(f"Empty truck name in line: {line}")
                return None

            # Create the event (no time information available)
            return FoodTruckEvent(
                brewery_key=self.brewery.key,
                brewery_name=self.brewery.name,
                food_truck_name=truck_name,
                date=date,
                start_time=None,  # No time info available
                end_time=None,  # No time info available
                ai_generated_name=False,
            )

        except Exception as e:
            self.logger.debug(f"Error parsing line '{line}': {str(e)}")
            return None

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse date string in M/D format (e.g., "7/3")
        """
        try:
            # Split the date string
            parts = date_str.split("/")
            if len(parts) != 2:
                return None

            month, day = map(int, parts)

            # Validate month and day
            if not (1 <= month <= 12) or not (1 <= day <= 31):
                return None

            # Determine the year using Pacific timezone - assume current year, but if month has passed, use next year
            current_year = get_pacific_year()
            current_month = get_pacific_month()

            # If the month is before current month, assume next year
            if month < current_month:
                current_year += 1

            return parse_date_with_pacific_context(current_year, month, day)

        except (ValueError, TypeError) as e:
            self.logger.debug(f"Error parsing date '{date_str}': {str(e)}")
            return None
