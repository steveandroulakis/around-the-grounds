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

from ..models import Event
from ..utils.timezone_utils import (
    get_pacific_year,
    parse_date_with_pacific_context,
)
from .base import BaseParser


class ChannelMarkerParser(BaseParser):
    """Parser for Channel Marker Cider food truck schedule."""

    # "5PM-8PM", "5:30PM-8PM", "11AM-3PM", "5-8PM" (start period optional).
    TIME_RANGE_PATTERN = re.compile(
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)?\s*[-–—]\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*(AM|PM)",
        re.IGNORECASE,
    )

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        """Parse food truck events from Google Sheets CSV."""
        try:
            csv_data = await self._fetch_csv(session, self.venue.url)
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
            self.logger.error(f"Error parsing {self.venue.name}: {str(e)}")
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

    def _parse_csv_row(self, row: List[str]) -> Optional[Event]:
        """Parse a single CSV row into an Event.

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
        food_truck_name = self._title_case(row[1]) if len(row) > 1 else ""
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

        return Event(
            venue_key=self.venue.key,
            venue_name=self.venue.name,
            title=food_truck_name,
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            description=None,
            extraction_method="csv",
        )

    def _title_case(self, name: str) -> str:
        """Title-case an ALL-CAPS name without capitalizing after apostrophes.

        `str.title()` turns "FINN ANTHONY'S" into "Finn Anthony'S".
        """
        return re.sub(
            r"[A-Za-z]+(?:'[A-Za-z]+)*",
            lambda m: m.group(0).capitalize(),
            name.strip(),
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
        """Parse a range like '5PM-8PM' or '5:30PM-8PM' into start/end times.

        The sheet mixes whole-hour ("6PM-9PM") and half-hour ("5:30PM-8PM")
        entries, and sometimes omits the period on the start ("5-8PM"), so the
        minutes and the leading AM/PM are both optional.
        """
        if not time_str:
            return None, None

        match = self.TIME_RANGE_PATTERN.search(time_str)
        if not match:
            return None, None

        start_hour = int(match.group(1))
        start_minute = int(match.group(2) or 0)
        start_period = match.group(3).upper() if match.group(3) else None
        end_hour = int(match.group(4))
        end_minute = int(match.group(5) or 0)
        end_period = match.group(6).upper()

        if start_minute > 59 or end_minute > 59:
            return None, None

        end_hour_24 = self._to_24h(end_hour, end_period)
        if end_hour_24 is None:
            return None, None

        if start_period is None:
            start_hour_24 = self._infer_start_hour(
                start_hour, start_minute, end_hour_24, end_minute, end_period
            )
        else:
            start_hour_24 = self._to_24h(start_hour, start_period)

        if start_hour_24 is None:
            return None, None

        start_time = event_date.replace(
            hour=start_hour_24, minute=start_minute, second=0, microsecond=0
        )
        end_time = event_date.replace(
            hour=end_hour_24, minute=end_minute, second=0, microsecond=0
        )

        return start_time, end_time

    def _infer_start_hour(
        self,
        start_hour: int,
        start_minute: int,
        end_hour_24: int,
        end_minute: int,
        end_period: str,
    ) -> Optional[int]:
        """Infer the AM/PM of a start time that omits it, e.g. '11-3PM'.

        Assume the start shares the end's period; if that would put the start
        at or after the end, fall back to the other period.
        """
        same_period = self._to_24h(start_hour, end_period)
        if same_period is None:
            return None
        if (same_period, start_minute) < (end_hour_24, end_minute):
            return same_period

        other = "AM" if end_period == "PM" else "PM"
        other_period = self._to_24h(start_hour, other)
        if other_period is not None and (other_period, start_minute) < (
            end_hour_24,
            end_minute,
        ):
            return other_period

        return same_period

    def _to_24h(self, hour: int, period: str) -> Optional[int]:
        """Convert 12-hour time to 24-hour."""
        if hour < 1 or hour > 12:
            return None
        if period == "AM":
            return 0 if hour == 12 else hour
        else:  # PM
            return hour if hour == 12 else hour + 12
