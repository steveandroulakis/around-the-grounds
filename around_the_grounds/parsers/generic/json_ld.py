"""Generic JSON-LD parser for Schema.org Event data.

Triggered by source_type: "json-ld". Extracts events from
<script type="application/ld+json"> tags in HTML pages.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ...models import Event, Venue
from ..base import BaseParser

# Schema.org Event type and common subtypes
_DEFAULT_EVENT_TYPES = [
    "Event",
    "MusicEvent",
    "ComedyEvent",
    "TheaterEvent",
    "DanceEvent",
    "SportsEvent",
    "FoodEvent",
    "Festival",
    "ScreeningEvent",
    "SocialEvent",
    "EducationEvent",
    "BusinessEvent",
    "ExhibitionEvent",
]


class JsonLdParser(BaseParser):
    """Generic parser for sites embedding Schema.org JSON-LD event data."""

    def __init__(self, venue: Venue) -> None:
        super().__init__(venue)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        config = self.venue.parser_config or {}
        event_types: List[str] = config.get(
            "event_types", _DEFAULT_EVENT_TYPES
        )
        field_map: Dict[str, str] = config.get("field_map", {})

        soup = await self.fetch_page(session, self.venue.url)
        ld_scripts = soup.find_all("script", type="application/ld+json")

        if not ld_scripts:
            self.logger.info(
                f"JsonLdParser: no JSON-LD scripts found at {self.venue.url}"
            )
            return []

        events: List[Event] = []
        for script in ld_scripts:
            try:
                data = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                self.logger.debug(
                    "JsonLdParser: skipping malformed JSON-LD block"
                )
                continue
            events.extend(self._extract_events(data, event_types, field_map))

        self.logger.info(
            f"JsonLdParser: {len(events)} events from {self.venue.url}"
        )
        return events

    def _extract_events(
        self,
        data: Any,
        event_types: List[str],
        field_map: Dict[str, str],
    ) -> List[Event]:
        """Recursively find event objects in JSON-LD data."""
        results: List[Event] = []

        if isinstance(data, list):
            for item in data:
                results.extend(
                    self._extract_events(item, event_types, field_map)
                )
            return results

        if not isinstance(data, dict):
            return results

        # Handle @graph wrapper
        if "@graph" in data:
            results.extend(
                self._extract_events(data["@graph"], event_types, field_map)
            )
            return results

        # Check if this dict is an event type
        ld_type = data.get("@type", "")
        if isinstance(ld_type, list):
            type_match = any(t in event_types for t in ld_type)
        else:
            type_match = ld_type in event_types

        if type_match:
            event = self._map_event(data, field_map)
            if event:
                results.append(event)

        return results

    def _map_event(
        self, data: Dict[str, Any], field_map: Dict[str, str]
    ) -> Optional[Event]:
        """Map a JSON-LD event dict to an Event model."""
        try:
            title_key = field_map.get("title", "name")
            title = str(data.get(title_key, "")).strip()
            if not title:
                return None

            start_key = field_map.get("date", "startDate")
            start_str = str(data.get(start_key, "")).strip()
            if not start_str:
                return None
            start_dt = self._parse_iso(start_str)
            if not start_dt:
                return None

            end_key = field_map.get("end_time", "endDate")
            end_dt: Optional[datetime] = None
            end_str = str(data.get(end_key, "")).strip()
            if end_str:
                end_dt = self._parse_iso(end_str)

            desc_key = field_map.get("description", "description")
            description = str(data.get(desc_key, "")).strip() or None

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=start_dt,
                start_time=start_dt,
                end_time=end_dt,
                description=description,
                extraction_method="json-ld",
            )
        except Exception as e:
            self.logger.debug(f"JsonLdParser: error mapping event: {e}")
            return None

    def _parse_iso(self, text: str) -> Optional[datetime]:
        """Parse ISO 8601 datetime string."""
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
