import html
import json
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

from ..models import Event
from ..utils.timezone_utils import now_in_pacific_naive
from .base import BaseParser


class LuckyEnvelopeParser(BaseParser):
    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        try:
            soup = await self.fetch_page(session, self.venue.url)
            items = self._extract_user_items(soup)
            events = []
            for item in items:
                event = self._parse_event(item)
                if event:
                    events.append(event)
            valid_events = self.filter_valid_events(events)
            self.logger.info(
                f"Parsed {len(valid_events)} valid events from {len(items)} items"
            )
            return valid_events
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                f"Failed to parse Lucky Envelope Brewing website: {str(e)}"
            )

    def _extract_user_items(self, soup: Any) -> List[Any]:
        try:
            carousel = soup.find(
                "div",
                class_=lambda c: c and "user-items-list-carousel" in c.split(),
                attrs={"data-current-context": True},
            )
            if not carousel:
                self.logger.warning(
                    "No carousel element with data-current-context found"
                )
                return []

            raw_attr = carousel.get("data-current-context", "")
            decoded = html.unescape(raw_attr)
            data: Any = json.loads(decoded)
            items: List[Any] = data.get("userItems", [])
            return items
        except Exception as e:
            self.logger.warning(f"Failed to extract userItems: {str(e)}")
            return []

    def _parse_event(self, item: dict) -> Optional[Event]:
        try:
            title = item.get("title", "").strip()
            if not title:
                return None

            description_html = item.get("description", "")
            desc_soup = BeautifulSoup(description_html, "html.parser")
            paragraphs = [p.get_text(strip=True) for p in desc_soup.find_all("p")]

            if not paragraphs:
                return None

            date_text = paragraphs[0] if len(paragraphs) > 0 else ""
            time_text = paragraphs[1] if len(paragraphs) > 1 else ""

            event_date = self._parse_date(date_text)
            if not event_date:
                self.logger.warning(f"Could not parse date from: {date_text!r}")
                return None

            start_dt, end_dt = self._parse_time_range(time_text, event_date)

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=event_date,
                start_time=start_dt,
                end_time=end_dt,
                description=None,
                extraction_method="html",
            )
        except Exception as e:
            self.logger.warning(f"Failed to parse event item: {str(e)}")
            return None

    def _parse_date(self, text: str) -> Optional[datetime]:
        match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
        if not match:
            return None
        month = int(match.group(1))
        day = int(match.group(2))
        year = int(match.group(3))
        if year < 100:
            year += 2000
        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    def _parse_time_range(
        self, text: str, event_date: datetime
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        pattern = (
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*[-–—]\s*"
            r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
        )
        match = re.search(pattern, text.lower().strip())
        if not match:
            return (None, None)

        start_h = int(match.group(1))
        start_m = int(match.group(2)) if match.group(2) else 0
        start_ampm = match.group(3)
        end_h = int(match.group(4))
        end_m = int(match.group(5)) if match.group(5) else 0
        end_ampm = match.group(6)

        # Inherit am/pm from end time if start lacks it
        if start_ampm is None and end_ampm is not None:
            start_ampm = end_ampm

        def to_24h(hour: int, minute: int, ampm: Optional[str]) -> Optional[datetime]:
            try:
                if ampm == "pm" and hour != 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0
                return event_date.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            except ValueError:
                return None

        start_dt = to_24h(start_h, start_m, start_ampm)
        end_dt = to_24h(end_h, end_m, end_ampm)
        return (start_dt, end_dt)
