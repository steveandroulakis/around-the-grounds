"""Generic CSS-selector-driven HTML parser.

Triggered by source_type: "html" when no venue-specific parser is registered.
Extracts events using configurable CSS selectors from parser_config.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
from bs4 import BeautifulSoup, Tag

from ...models import Event, Venue
from ..base import BaseParser


class HtmlSelectorParser(BaseParser):
    """Generic parser using CSS selectors from venue.parser_config."""

    def __init__(self, venue: Venue) -> None:
        super().__init__(venue)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        config = self.venue.parser_config or {}

        event_container = config.get("event_container", ".event-item")
        title_selector = config.get("title_selector", ".event-title")
        date_selector = config.get("date_selector", ".event-date")
        date_attribute: Optional[str] = config.get("date_attribute")
        time_selector: Optional[str] = config.get("time_selector")
        desc_selector: Optional[str] = config.get("description_selector")
        date_format: str = config.get("date_format", "auto")

        soup = await self.fetch_page(session, self.venue.url)

        containers = soup.select(event_container)
        if not containers:
            self.logger.info(
                f"HtmlSelectorParser: no containers matching '{event_container}' "
                f"at {self.venue.url}"
            )
            return []

        events: List[Event] = []
        for container in containers:
            event = self._parse_container(
                container,
                title_selector=title_selector,
                date_selector=date_selector,
                date_attribute=date_attribute,
                time_selector=time_selector,
                desc_selector=desc_selector,
                date_format=date_format,
            )
            if event:
                events.append(event)

        self.logger.info(
            f"HtmlSelectorParser: {len(events)} events from {self.venue.url}"
        )
        return events

    def _parse_container(
        self,
        container: Tag,
        title_selector: str,
        date_selector: str,
        date_attribute: Optional[str],
        time_selector: Optional[str],
        desc_selector: Optional[str],
        date_format: str,
    ) -> Optional[Event]:
        """Extract a single Event from one HTML container."""
        try:
            title_el = container.select_one(title_selector)
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            if not title:
                return None

            date_el = container.select_one(date_selector)
            if not date_el:
                return None
            if date_attribute:
                date_text = str(date_el.get(date_attribute, "")).strip()
            else:
                date_text = date_el.get_text(separator=" ", strip=True)
            date = self._parse_date(date_text, date_format)
            if not date:
                return None

            start_time: Optional[datetime] = None
            end_time: Optional[datetime] = None
            if time_selector:
                time_el = container.select_one(time_selector)
                if time_el:
                    start_time, end_time = self._parse_time_range(
                        time_el.get_text(strip=True), date
                    )

            description: Optional[str] = None
            if desc_selector:
                desc_el = container.select_one(desc_selector)
                if desc_el:
                    description = desc_el.get_text(strip=True) or None

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=date,
                start_time=start_time,
                end_time=end_time,
                description=description,
                extraction_method="html",
            )
        except Exception as e:
            self.logger.debug(f"Error parsing container: {e}")
            return None

    def _parse_date(self, text: str, date_format: str) -> Optional[datetime]:
        """Parse a date string using the configured format or dateutil auto-parse."""
        text = text.strip()
        if not text:
            return None
        if date_format == "auto":
            try:
                from dateutil import parser as dateutil_parser

                return dateutil_parser.parse(text, fuzzy=True)
            except Exception:
                return None
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            return None

    @staticmethod
    def _extract_period(text: str) -> Optional[str]:
        """Extract AM/PM period from a time string, if present."""
        import re

        m = re.search(r"(am|pm)", text, re.IGNORECASE)
        return m.group(1).lower() if m else None

    def _parse_time_range(
        self, text: str, date: datetime
    ) -> tuple:
        """Parse a time range like '7:00 PM - 10:00 PM' relative to date.

        Carries forward AM/PM from the start part when the end part lacks it,
        e.g. '5pm-8:30' → start=17:00, end=20:30.
        """
        import re

        parts = re.split(r"\s*[-–—]\s*", text, maxsplit=1)
        start_time: Optional[datetime] = None
        end_time: Optional[datetime] = None

        start_period: Optional[str] = None
        if parts:
            start_period = self._extract_period(parts[0])
            start_time = self._parse_single_time(parts[0].strip(), date)

        if len(parts) > 1:
            end_time = self._parse_single_time(
                parts[1].strip(), date, default_period=start_period
            )

        return start_time, end_time

    def _parse_single_time(
        self,
        text: str,
        date: datetime,
        default_period: Optional[str] = None,
    ) -> Optional[datetime]:
        """Parse a single time string like '7:00 PM' relative to date.

        When the text has no AM/PM suffix and *default_period* is provided,
        the default is used instead (enables carry-forward from the start time).
        """
        import re

        m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)?", text, re.IGNORECASE)
        if not m:
            m = re.search(r"(\d{1,2})\s*(am|pm)", text, re.IGNORECASE)
            if not m:
                return None
            hour = int(m.group(1))
            minute = 0
            period: Optional[str] = m.group(2).lower()
        else:
            hour = int(m.group(1))
            minute = int(m.group(2))
            period = m.group(3).lower() if m.group(3) else default_period

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        try:
            return date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except ValueError:
            return None
