"""
Chuck's Hop Shop Greenwood parser.

Parses food truck schedule from Google Sheets CSV export.
Handles redirects, filters events, and processes meal categories.
"""

import csv
import io
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


class GoogleSheetsCsvParser(BaseParser):
    """
    Parser for Google Sheets CSV exports.

    Handles Google Sheets published as CSV with automatic monthly updates.
    Can be used by any site that publishes event data via Google Sheets CSV export.
    """

    # Month abbreviation to number mapping
    MONTH_MAP = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        """Parse food truck events from Google Sheets CSV."""
        try:
            csv_data = await self._fetch_csv(session, self.brewery.url)
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
            self.logger.error(f"Error parsing {self.brewery.name}: {str(e)}")
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

    def _parse_csv_row(self, row: List[str]) -> Optional[FoodTruckEvent]:
        """Parse a single CSV row into a FoodTruckEvent."""
        # Actual CSV structure (from real data):
        # Column A (0): Day of Week ("Fri", "Sat", "Sun")
        # Column B (1): Month+Date ("Aug 1", "Sep 15", "Oct 31")
        # Column C (2): Time ("12 AM")
        # Column D (3): "to"
        # Column E (4): End Day
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

        # Parse date from columns A and B (day of week and "Month Date")
        event_date = self._parse_date_from_month_date_column(row[0], row[1])
        if not event_date:
            self.logger.debug(
                f"Could not parse date from: {row[0]}, {row[1]}, {row[2]}"
            )
            return None

        return FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name=food_truck_name,
            date=event_date,
            start_time=None,  # Times are placeholder "12 AM" in the data
            end_time=None,
            description=f"Original event: {event_name}",
            ai_generated_name=False,
        )

    def _extract_vendor_name(self, event_name: str) -> Optional[str]:
        """Extract vendor name from event name, handling meal type prefixes."""
        if not event_name or not event_name.strip():
            return None

        # Handle format like "Dinner: T'Juana" or "Brunch: Good Morning Tacos"
        if ":" in event_name:
            parts = event_name.split(":", 1)
            if len(parts) == 2:
                meal_type = parts[0].strip()
                vendor_name = parts[1].strip()

                # Validate meal type
                if meal_type.lower() in ["brunch", "dinner"]:
                    return vendor_name if vendor_name else None
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
            if month_abbr not in self.MONTH_MAP:
                self.logger.debug(f"Unknown month abbreviation: {month_abbr}")
                return None

            month_num = self.MONTH_MAP[month_abbr]

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

            # Create date using Pacific timezone context
            return parse_date_with_pacific_context(year, month_num, day_num)

        except Exception as e:
            self.logger.debug(
                f"Error parsing date from {day_col}, {month_date_col}: {str(e)}"
            )
            return None
