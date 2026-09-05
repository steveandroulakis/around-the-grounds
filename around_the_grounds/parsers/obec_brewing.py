import re
from datetime import datetime
from typing import List, Optional, Tuple

import aiohttp

from ..models import Event
from ..utils.timezone_utils import now_in_pacific_naive
from .base import BaseParser


class ObecBrewingParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        try:
            soup = await self.fetch_page(session, self.venue.url)
            events = []

            if not soup:
                raise ValueError("Failed to fetch page content")

            # Get all text content from the page
            page_text = soup.get_text()

            # Use the regex pattern from config to find food truck information
            # Pattern: "Food truck:\s*([^0-9]+)\s*([0-9:]+\s*-\s*[0-9:]+)"
            parser_config = self.venue.parser_config or {}
            pattern = parser_config.get(
                "pattern",
                r"Food truck:\s*([^0-9]+)\s*(\d{1,2}(?::\d{2})?\s*(?:[ap]m)?"
                r"\s*[-–—]\s*\d{1,2}(?::\d{2})?\s*(?:[ap]m)?)",
            )

            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                truck_name = match.group(1).strip()
                time_range = match.group(2).strip()

                # Parse the time range (e.g., "4:00 - 8:00")
                start_time, end_time = self._parse_time_range(time_range)

                # Create event for today in Pacific timezone
                today = now_in_pacific_naive().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )

                event = Event(
                    venue_key=self.venue.key,
                    venue_name=self.venue.name,
                    title=truck_name,
                    date=today,
                    start_time=start_time,
                    end_time=end_time,
                    extraction_method="html",
                )
                events.append(event)

            # Filter and validate events
            valid_events = self.filter_valid_events(events)
            self.logger.info(
                f"Parsed {len(valid_events)} valid events from {len(events)} total"
            )
            return valid_events

        except Exception as e:
            self.logger.error(f"Error parsing Obec Brewing: {str(e)}")
            raise ValueError(f"Failed to parse Obec Brewing website: {str(e)}")

    def _parse_time_range(
        self, time_range: str
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse time range like '4:00 - 8:00' into start and end datetime objects."""
        try:
            # Split on dash/hyphen
            time_parts = re.split(r"\s*[-–—]\s*", time_range)
            if len(time_parts) != 2:
                return None, None

            start_str, end_str = time_parts

            # Parse individual times
            start_time = self._parse_single_time(start_str.strip())
            end_time = self._parse_single_time(end_str.strip())

            if start_time and end_time:
                today = now_in_pacific_naive().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                start_datetime = today.replace(hour=start_time[0], minute=start_time[1])
                end_datetime = today.replace(hour=end_time[0], minute=end_time[1])
                return start_datetime, end_datetime

            return None, None

        except Exception as e:
            self.logger.warning(f"Failed to parse time range '{time_range}': {str(e)}")
            return None, None

    def _parse_single_time(self, time_str: str) -> Optional[Tuple[int, int]]:
        """Parse a single time like '4:00' or '16:00' into (hour, minute)."""
        try:
            # Handle formats like "4:00", "16:00", "4", etc.
            time_match = re.fullmatch(
                r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)?", time_str, re.IGNORECASE
            )
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2)) if time_match.group(2) else 0

                meridiem = time_match.group(3)
                if meridiem:
                    if not 1 <= hour <= 12:
                        return None
                    hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
                elif 1 <= hour <= 11 and not time_match.group(1).startswith("0"):
                    # Obec publishes afternoon/evening food-truck service with
                    # omitted AM/PM. Treat unqualified 1-11 as PM; explicit
                    # AM/PM, noon, and zero-padded/24-hour times take precedence.
                    hour += 12

                # Validate hour range
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return (hour, minute)

            return None

        except Exception:
            return None
