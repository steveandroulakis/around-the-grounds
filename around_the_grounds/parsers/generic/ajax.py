"""Generic AJAX/JSON API parser.

Triggered by source_type: "ajax". Attempts to fetch events from a JSON
endpoint, optionally scanning the page source for the endpoint URL if
api_url is not provided.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ...models import Event, Venue
from ..base import BaseParser


def _dig(obj: Any, path: str) -> Any:
    """Traverse obj using dot-notation path (e.g. 'data.events')."""
    for key in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (IndexError, ValueError):
                return None
        else:
            return None
        if obj is None:
            return None
    return obj


class AjaxParser(BaseParser):
    """Generic parser for sites that expose events via an AJAX/JSON endpoint."""

    def __init__(self, venue: Venue) -> None:
        super().__init__(venue)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        config = self.venue.parser_config or {}
        api_url: Optional[str] = config.get("api_url")
        method: str = config.get("method", "GET").upper()
        params: Dict[str, Any] = dict(config.get("params", {}))
        response_path: Optional[str] = config.get("response_path")
        field_map: Dict[str, str] = config.get("field_map", {})

        # Resolve date placeholders like {{today_iso}} and {{end_date_iso}}
        params = self._resolve_date_placeholders(params)

        # Discover the endpoint if not explicitly configured
        if not api_url:
            api_url = await self._discover_endpoint(session)

        if not api_url:
            self.logger.warning(
                f"AjaxParser: no API endpoint found for {self.venue.url}; "
                "returning empty list"
            )
            return []

        self.logger.debug(f"AjaxParser: fetching {api_url}")

        try:
            if method == "POST":
                async with session.post(api_url, json=params) as response:
                    if response.status != 200:
                        raise ValueError(f"HTTP {response.status}: {api_url}")
                    data = await response.json(content_type=None)
            else:
                async with session.get(api_url, params=params or None) as response:
                    if response.status != 200:
                        raise ValueError(f"HTTP {response.status}: {api_url}")
                    data = await response.json(content_type=None)
        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching {api_url}: {e}")

        # Traverse to the events array
        events_data: Any = _dig(data, response_path) if response_path else data
        if events_data is None:
            self.logger.warning(
                f"AjaxParser: response_path '{response_path}' returned None"
            )
            return []

        if not isinstance(events_data, list):
            self.logger.warning(
                f"AjaxParser: expected list at path '{response_path}', "
                f"got {type(events_data).__name__}"
            )
            return []

        events: List[Event] = []
        for item in events_data:
            event = self._map_item(item, field_map)
            if event:
                events.append(event)

        self.logger.info(f"AjaxParser: {len(events)} events from {api_url}")
        return events

    def _map_item(
        self, item: Dict[str, Any], field_map: Dict[str, str]
    ) -> Optional[Event]:
        """Map a raw response item to an Event using field_map."""
        try:
            # title
            title_key = field_map.get("title", "name")
            title = str(item.get(title_key, "")).strip()
            if not title:
                return None

            # date
            date_key = field_map.get("date", "start")
            date_str = str(item.get(date_key, "")).strip()
            if not date_str:
                return None
            date = self._parse_datetime(date_str)
            if not date:
                return None

            # optional times
            start_key = field_map.get("start_time", "start_time")
            end_key = field_map.get("end_time", "end_time")
            start_time = self._parse_datetime(str(item.get(start_key, "")))
            end_time = self._parse_datetime(str(item.get(end_key, "")))

            # description
            desc_key = field_map.get("description", "description")
            description: Optional[str] = str(item.get(desc_key, "")).strip() or None

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=date,
                start_time=start_time,
                end_time=end_time,
                description=description,
                extraction_method="api",
            )
        except Exception as e:
            self.logger.debug(f"AjaxParser: error mapping item: {e}")
            return None

    def _parse_datetime(self, text: str) -> Optional[datetime]:
        """Parse ISO or human-readable datetime strings."""
        text = text.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        try:
            from dateutil import parser as dateutil_parser

            return dateutil_parser.parse(text, fuzzy=True)
        except Exception:
            return None

    def _resolve_date_placeholders(
        self, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Replace {{today_iso}} and {{end_date_iso}} with actual UTC dates."""
        from datetime import timedelta

        now = datetime.utcnow()
        end = now + timedelta(days=7)
        today_iso = now.strftime("%Y-%m-%dT00:00:00.000Z")
        end_iso = end.strftime("%Y-%m-%dT23:59:59.999Z")

        resolved: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, str):
                v = v.replace("{{today_iso}}", today_iso)
                v = v.replace("{{end_date_iso}}", end_iso)
            resolved[k] = v
        return resolved

    async def _discover_endpoint(
        self, session: aiohttp.ClientSession
    ) -> Optional[str]:
        """Scan the page source for AJAX endpoint URLs."""
        try:
            async with session.get(self.venue.url) as response:
                if response.status != 200:
                    return None
                html = await response.text()
        except aiohttp.ClientError as e:
            self.logger.warning(
                f"AjaxParser: could not fetch page for endpoint discovery: {e}"
            )
            return None

        # Look for JSON API URLs in inline JS (simple heuristic)
        patterns = [
            r'https?://[^\s"\']+/api/events[^\s"\']*',
            r'https?://api\.[^\s"\']+/events[^\s"\']*',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, html)
            if matches:
                return matches[0]

        return None
