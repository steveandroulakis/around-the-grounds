"""
Channel Marker Cider parser.

Parses food truck schedule from Google Sheets CSV export.
Simple 4-column format: DATE, FOOD TRUCK, TIME, EVENT.
"""

import csv
import io
import re
from datetime import datetime
from typing import List, Optional, Tuple

import aiohttp

from ..models import FoodTruckEvent
from ..utils.timezone_utils import (
    get_pacific_year,
    parse_date_with_pacific_context,
)
from .base import BaseParser


class ChannelMarkerParser(BaseParser):
    """Parser for Channel Marker Cider food truck schedule."""

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        """Parse food truck events from Google Sheets CSV."""
        try:
            csv_data = await self._fetch_csv(session, self.brewery.url)
            if not csv_data:
                raise ValueError("Failed to fetch CSV data")

            events = []

            csv_reader = csv.reader(io.StringIO(csv_data))
            rows = list(csv_reader)

            if not rows:
                self.logger.warning("CSV data is empty")
                return []

            # Skip header row if present
            data_rows = rows[1:] if len(rows) > 1 else rows

            for row_num, row in enumerate(data_rows, start=2):
                try:
                    event = self._parse_csv_row(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.logger.debug(f"Error parsing row {row_num}: {row} - {str(e)}")
                    continue

            valid_events = self.filter_valid_events(events)
            self.logger.info(
                f"Parsed {len(valid_events)} valid events from {len(data_rows)} rows"
            )
            return valid_events

        except Exception as e:
            self.logger.error(f"Error parsing {self.brewery.name}: {str(e)}")
            raise ValueError(f"Failed to parse CSV data: {str(e)}")

    async def _fetch_csv(
        self, session: aiohttp.ClientSession, url: str
    ) -> Optional[str]:
        """Fetch CSV data from URL, handling redirects."""
        try:
            self.logger.debug(f"Fetching CSV from: {url}")

            async with session.get(url, allow_redirects=True) as response:
                if response.status == 404:
                    raise ValueError(f"CSV not found (404): {url}")
                elif response.status == 403:
                    raise ValueError(f"Access forbidden (403): {url}")
                elif response.status == 500:
                    raise ValueError(f"Server error (500): {url}")
                elif response.status != 200:
                    raise ValueError(f"HTTP {response.status}: {url}")

                content = await response.text()

                if not content or len(content.strip()) == 0:
                    raise ValueError(f"Empty CSV response from: {url}")

                if str(response.url) != url:
                    self.logger.debug(f"CSV redirected to: {response.url}")

                return content

        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching CSV {url}: {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Failed to fetch CSV from {url}: {str(e)}")

    def _parse_csv_row(self, row: List[str]) -> Optional[FoodTruckEvent]:
        """Parse a single CSV row into a FoodTruckEvent.

        Expected CSV columns:
        Column 0 (DATE): "3/31/26" (M/D/YY format)
        Column 1 (FOOD TRUCK): "WHERE YA AT, MATT?"
        Column 2 (TIME): "5PM-8PM"
        Column 3 (EVENT): "MUSIC BINGO (7-9PM)" or "N/A"
        """
        if len(row) < 2:
            return None

        # Skip empty rows
        if not any(cell.strip() for cell in row[:2]):
            return None

        # Extract food truck name (Column 1), converting to title case
        food_truck_name = row[1].strip().title() if len(row) > 1 else ""
        if not food_truck_name:
            return None

        # Parse date (Column 0)
        date_str = row[0].strip() if row[0] else ""
        event_date = self._parse_date(date_str)
        if not event_date:
            self.logger.debug(f"Could not parse date from: {date_str}")
            return None

        # Parse time range (Column 2)
        time_str = row[2].strip() if len(row) > 2 else ""
        start_time, end_time = self._parse_time_range(time_str, event_date)

        return FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name=food_truck_name,
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            description=None,
            ai_generated_name=False,
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from M/D/YY or M/D format."""
        if not date_str:
            return None

        try:
            parts = date_str.split("/")
            if len(parts) == 3:
                month = int(parts[0])
                day = int(parts[1])
                year = int(parts[2])
                # Handle 2-digit year
                if year < 100:
                    year += 2000
            elif len(parts) == 2:
                month = int(parts[0])
                day = int(parts[1])
                year = get_pacific_year()
            else:
                return None

            if not (1 <= month <= 12) or not (1 <= day <= 31):
                return None

            return parse_date_with_pacific_context(year, month, day)

        except (ValueError, IndexError):
            return None

    def _parse_time_range(
        self, time_str: str, event_date: datetime
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse time range like '5PM-8PM' into start/end datetimes."""
        if not time_str:
            return None, None

        # Match patterns like "5PM-8PM", "11AM-3PM", "5pm-8pm"
        match = re.match(
            r"(\d{1,2})\s*(AM|PM)\s*-\s*(\d{1,2})\s*(AM|PM)",
            time_str,
            re.IGNORECASE,
        )
        if not match:
            return None, None

        start_hour = int(match.group(1))
        start_period = match.group(2).upper()
        end_hour = int(match.group(3))
        end_period = match.group(4).upper()

        start_hour_24 = self._to_24h(start_hour, start_period)
        end_hour_24 = self._to_24h(end_hour, end_period)

        if start_hour_24 is None or end_hour_24 is None:
            return None, None

        start_time = event_date.replace(hour=start_hour_24, minute=0, second=0)
        end_time = event_date.replace(hour=end_hour_24, minute=0, second=0)

        return start_time, end_time

    def _to_24h(self, hour: int, period: str) -> Optional[int]:
        """Convert 12-hour time to 24-hour."""
        if hour < 1 or hour > 12:
            return None
        if period == "AM":
            return 0 if hour == 12 else hour
        else:  # PM
            return hour if hour == 12 else hour + 12
