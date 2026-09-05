"""
Chuck's Hop Shop Greenwood parser.

Parses food truck schedule from Google Sheets CSV export.
Handles redirects, filters events, and processes meal categories.

Reads the published spreadsheet's "Greenwood" tab (gid=1258996532), whose
columns C and E carry real start/end hours. The sibling "GW Mobile" tab
(gid=1143085558) renders those same columns as "12 AM" and a day-of-week,
so it cannot supply times.
"""

import csv
import io
import re
from datetime import date, datetime
from typing import List, Optional, Tuple

import aiohttp

from ..models import Event
from ..utils.date_utils import MONTH_ABBREVIATIONS, WEEKDAY_ABBREVIATIONS
from ..utils.timezone_utils import (
    get_pacific_month,
    get_pacific_year,
    parse_date_with_pacific_context,
)
from .base import BaseParser


class ChucksGreenwoodParser(BaseParser):
    """Parser for Chuck's Hop Shop Greenwood food truck schedule."""

    # Google Sheets formula error tokens that can appear in the source
    # spreadsheet's cells (e.g. when a lookup formula fails). These must never
    # be treated as vendor names. Compared case-insensitively.
    SPREADSHEET_ERROR_VALUES = frozenset(
        {
            "#value!",
            "#ref!",
            "#n/a",
            "#name?",
            "#div/0!",
            "#null!",
            "#num!",
            "#error!",
            "#getting_data",
        }
    )

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        """Parse food truck events from Google Sheets CSV."""
        try:
            csv_data = await self._fetch_csv(session, self.venue.url)
            if not csv_data:
                raise ValueError("Failed to fetch CSV data")

            events = []

            # Parse CSV data
            csv_reader = csv.reader(io.StringIO(csv_data))
            rows = list(csv_reader)

            if not rows:
                self.logger.warning("CSV data is empty")
                return []

            # Skip header row if present
            data_rows = rows[1:] if len(rows) > 1 else rows

            for row_num, row in enumerate(data_rows, start=2):  # Start at 2 for header
                try:
                    event = self._parse_csv_row(row)
                    if event:
                        events.append(event)
                except Exception as e:
                    self.logger.debug(f"Error parsing row {row_num}: {row} - {str(e)}")
                    continue

            # Filter and validate events
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

            # Allow redirects for Google Sheets → CDN
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

                # Log redirect for debugging
                if str(response.url) != url:
                    self.logger.debug(f"CSV redirected to: {response.url}")

                return content

        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching CSV {url}: {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise  # Re-raise our custom ValueError messages
            raise ValueError(f"Failed to fetch CSV from {url}: {str(e)}")

    def _parse_csv_row(self, row: List[str]) -> Optional[Event]:
        """Parse a single CSV row into an Event."""
        # Actual CSV structure of the "Greenwood" tab (from real data):
        # Column A (0): Date ("9/4/2026") or, past ~2 months out, a day of
        #               week ("Fri", "Sat", "Sun")
        # Column B (1): Month+Date ("Aug 1", "Sep 15", "Nov 01")
        # Column C (2): Start hour ("17", "9")
        # Column D (3): "to"
        # Column E (4): End hour ("21", "12")
        # Column F (5): Event Type ("Food Truck", "Event")
        # Column G (6): Event Name ("Dinner: T'Juana", "Brunch: Good Morning Tacos")
        # ... additional columns

        if len(row) < 7:
            self.logger.debug(f"Row too short: {len(row)} columns, expected at least 7")
            return None

        # Skip empty rows
        if not any(cell.strip() for cell in row[:7]):
            return None

        # Filter for food truck events only (Column F)
        event_type = row[5].strip() if len(row) > 5 else ""
        if event_type != "Food Truck":
            self.logger.debug(
                f"Skipping non-food truck event: {row[6] if len(row) > 6 else 'Unknown'}"
            )
            return None

        # Extract event name (Column G)
        event_name = row[6].strip() if len(row) > 6 else ""
        if not event_name:
            self.logger.debug("Skipping row with empty event name")
            return None

        # Parse vendor name from event name
        food_truck_name = self._extract_vendor_name(event_name)
        if not food_truck_name:
            self.logger.debug(f"Could not extract vendor name from: {event_name}")
            return None

        # Parse date: prefer column A's explicit "M/D/YYYY", which needs no
        # year inference. Rows beyond ~2 months out hold a day of week there
        # instead, so fall back to column B's "Month Date".
        event_date = self._parse_full_date_column(row[0])
        if not event_date:
            event_date = self._parse_date_from_month_date_column(row[0], row[1])
        if not event_date:
            self.logger.debug(
                f"Could not parse date from: {row[0]}, {row[1]}, {row[2]}"
            )
            return None

        start_time, end_time = self._parse_hour_columns(row[2], row[4], event_date)

        return Event(
            venue_key=self.venue.key,
            venue_name=self.venue.name,
            title=food_truck_name,
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            description=f"Original event: {event_name}",
            extraction_method="html",
        )

    def _is_spreadsheet_error(self, value: str) -> bool:
        """Return True if a value is a Google Sheets formula error token."""
        return value.strip().lower() in self.SPREADSHEET_ERROR_VALUES

    def _extract_vendor_name(self, event_name: str) -> Optional[str]:
        """Extract vendor name from event name, handling meal type prefixes."""
        if not event_name or not event_name.strip():
            return None

        # Reject spreadsheet formula errors (e.g. "#VALUE!") that leak in from
        # the source Google Sheet — these are not real vendor names.
        if self._is_spreadsheet_error(event_name):
            return None

        # Handle format like "Dinner: T'Juana" or "Brunch: Good Morning Tacos"
        if ":" in event_name:
            parts = event_name.split(":", 1)
            if len(parts) == 2:
                meal_type = parts[0].strip()
                vendor_name = parts[1].strip()

                # Validate meal type
                if meal_type.lower() in ["brunch", "dinner"]:
                    if not vendor_name or self._is_spreadsheet_error(vendor_name):
                        return None
                    return vendor_name
                else:
                    # If not a recognized meal type, treat whole string as vendor name
                    cleaned_name = event_name.strip()
                    return cleaned_name if cleaned_name else None
            else:
                cleaned_name = event_name.strip()
                return cleaned_name if cleaned_name else None
        else:
            # No colon, treat as vendor name directly
            cleaned_name = event_name.strip()
            return cleaned_name if cleaned_name else None

    def _parse_date_from_month_date_column(
        self, day_col: str, month_date_col: str
    ) -> Optional[datetime]:
        """Parse date from the combined month+date column format."""
        try:
            # Clean inputs
            month_date_str = month_date_col.strip() if month_date_col else ""

            if not month_date_str:
                return None

            # Split "Aug 1" into ["Aug", "1"]
            parts = month_date_str.split()
            if len(parts) != 2:
                self.logger.debug(f"Invalid month+date format: {month_date_str}")
                return None

            month_abbr, date_str = parts

            # Convert month abbreviation to number
            month_key = month_abbr.lower()[:3]
            if month_key not in MONTH_ABBREVIATIONS:
                self.logger.debug(f"Unknown month abbreviation: {month_abbr}")
                return None

            month_num = MONTH_ABBREVIATIONS[month_key]

            # Parse day number
            try:
                day_num = int(date_str)
            except ValueError:
                self.logger.debug(f"Invalid day number: {date_str}")
                return None

            # Validate day range
            if not (1 <= day_num <= 31):
                return None

            # Determine appropriate year using Pacific timezone context
            current_year = get_pacific_year()
            current_month = get_pacific_month()

            # If the month is before current month, assume next year
            # This handles month rollover (e.g., parsing January dates in December)
            if month_num < current_month:
                year = current_year + 1
            else:
                year = current_year

            # The sheet keeps a stale block of prior-year rows below the
            # current schedule, and their month+day alone would land on
            # today's calendar as phantom duplicates. Column A names the
            # real weekday, so prefer the nearby year whose calendar agrees.
            year = self._year_matching_weekday(day_col, year, month_num, day_num)

            # Create date using Pacific timezone context
            return parse_date_with_pacific_context(year, month_num, day_num)

        except Exception as e:
            self.logger.debug(
                f"Error parsing date from {day_col}, {month_date_col}: {str(e)}"
            )
            return None

    def _year_matching_weekday(
        self, day_col: str, year: int, month: int, day: int
    ) -> int:
        """Pick the year whose calendar puts month/day on column A's weekday.

        Tries the inferred year first, then the neighbouring years. Returns
        the inferred year unchanged when column A is not a weekday we
        recognise, or when no candidate matches — a disagreeing weekday is
        more likely sheet sloppiness than a reason to discard the row.
        """
        weekday = day_col.strip().lower()[:3] if day_col else ""
        if weekday not in WEEKDAY_ABBREVIATIONS:
            return year

        target = WEEKDAY_ABBREVIATIONS[weekday]
        for candidate in (year, year - 1, year + 1):
            try:
                if date(candidate, month, day).weekday() == target:
                    return candidate
            except ValueError:
                continue  # e.g. Feb 29 in a non-leap candidate year

        self.logger.debug(
            f"No nearby year puts {month}/{day} on a {weekday}; "
            f"keeping inferred year {year}"
        )
        return year

    def _parse_full_date_column(self, date_col: str) -> Optional[datetime]:
        """Parse an explicit "M/D/YYYY" date from column A.

        The "Greenwood" tab fills this in for roughly the next two months and
        writes a day of week ("Sun", "Mon") beyond that; callers fall back to
        the month+date column when this returns None.
        """
        date_str = date_col.strip() if date_col else ""
        if not date_str:
            return None

        match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
        if not match:
            return None

        month, day, year = (int(g) for g in match.groups())

        if not (1 <= month <= 12) or not (1 <= day <= 31):
            self.logger.debug(f"Out-of-range date in column A: {date_str}")
            return None

        try:
            return parse_date_with_pacific_context(year, month, day)
        except ValueError:
            # e.g. 2/30 — a real calendar violation, not a format problem
            self.logger.debug(f"Invalid calendar date in column A: {date_str}")
            return None

    def _parse_hour_columns(
        self, start_col: str, end_col: str, event_date: datetime
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse the start/end hour columns into datetimes on the event date."""
        return (
            self._parse_hour_column(start_col, event_date),
            self._parse_hour_column(end_col, event_date),
        )

    def _parse_hour_column(
        self, value: str, event_date: datetime
    ) -> Optional[datetime]:
        """Parse a single hour-of-day cell ("17", "9", "17:30") onto a date.

        The sheet writes bare 24-hour integers today, but it is not our
        spreadsheet — accept "H:MM" too, and return None for anything else
        (including the "12 AM" the mobile tab emits) so the event still
        surfaces without a time rather than with a wrong one.
        """
        time_str = value.strip() if value else ""
        if not time_str:
            return None

        match = re.match(r"^(\d{1,2})(?::([0-5]\d))?$", time_str)
        if not match:
            self.logger.debug(f"Unrecognized hour column value: {value!r}")
            return None

        hour = int(match.group(1))
        minute = int(match.group(2) or 0)

        if not (0 <= hour <= 23):
            self.logger.debug(f"Out-of-range hour: {value!r}")
            return None

        return event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
