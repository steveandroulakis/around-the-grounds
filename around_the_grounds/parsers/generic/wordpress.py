"""Generic WordPress REST API parser.

Triggered by source_type: "wordpress". Supports any site running
the WordPress REST API (wp-json/wp/v2/posts) as well as sites using
The Events Calendar plugin (wp-json/tribe/events/v1/events).

Optionally filters by category_id or resolves category_slug to an ID
automatically. Supports response_path for wrapped responses and
field_map for custom field mapping.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp

from ...models import Event, Venue
from ..base import BaseParser


class WordPressParser(BaseParser):
    """Generic parser for sites using the WordPress REST API."""

    def __init__(self, venue: Venue) -> None:
        super().__init__(venue)
        self.logger = logging.getLogger(self.__class__.__name__)

    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        config = self.venue.parser_config or {}
        api_path = config.get("api_path", "/wp-json/wp/v2/posts")
        per_page = int(config.get("per_page", 20))
        category_id: Optional[int] = config.get("category_id")
        category_slug: Optional[str] = config.get("category_slug")
        response_path: Optional[str] = config.get("response_path")
        field_map: Optional[Dict[str, str]] = config.get("field_map")

        base_url = self.venue.url.rstrip("/")

        # Resolve category_slug to ID if needed
        if category_slug and not category_id:
            category_id = await self._resolve_category_slug(
                session, base_url, category_slug
            )

        # Build query params
        params: Dict[str, Any] = {
            "per_page": per_page,
            "_embed": "true",
        }
        if category_id:
            params["categories"] = category_id

        url = f"{base_url}{api_path}"
        self.logger.debug(f"Fetching WordPress API: {url} params={params}")

        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise ValueError(
                        f"WordPress API returned HTTP {response.status}: {url}"
                    )
                data = await response.json(content_type=None)
        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching WordPress API {url}: {e}")

        # Traverse response if response_path is set (e.g., Tribe Events)
        if response_path:
            from .ajax import _dig

            data = _dig(data, response_path)
            if data is None:
                self.logger.warning(
                    f"WordPressParser: response_path '{response_path}' "
                    "returned None"
                )
                return []

        if not isinstance(data, list):
            self.logger.warning(
                f"Unexpected WordPress API response shape for {url}"
            )
            return []

        events = []
        for item in data:
            if field_map:
                event = self._map_item(item, field_map)
            else:
                event = self._parse_post(item)
            if event:
                events.append(event)

        self.logger.info(f"WordPressParser: {len(events)} events from {base_url}")
        return events

    def _parse_post(self, post: Dict[str, Any]) -> Optional[Event]:
        """Map a WP post dict to an Event."""
        try:
            title_raw = post.get("title", {}).get("rendered", "")
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if not title:
                return None

            date_str = post.get("date", "")
            if not date_str:
                return None
            try:
                date = datetime.fromisoformat(date_str)
            except ValueError:
                self.logger.debug(f"Could not parse WP post date: {date_str!r}")
                return None

            excerpt_raw = post.get("excerpt", {}).get("rendered", "")
            description: Optional[str] = (
                re.sub(r"<[^>]+>", "", excerpt_raw).strip() or None
            )

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=date,
                start_time=None,
                end_time=None,
                description=description,
                extraction_method="api",
            )
        except Exception as e:
            self.logger.debug(f"Error parsing WP post: {e}")
            return None

    def _map_item(
        self, item: Dict[str, Any], field_map: Dict[str, str]
    ) -> Optional[Event]:
        """Map a response item to an Event using field_map.

        Handles both plain string titles and WP rendered objects
        (e.g., Tribe Events Calendar uses plain strings while
        vanilla WP uses {"rendered": "..."}).
        """
        try:
            title_key = field_map.get("title", "title")
            title_raw = item.get(title_key, "")
            # Handle both plain strings and WP rendered objects
            if isinstance(title_raw, dict):
                title_raw = title_raw.get("rendered", "")
            title = re.sub(r"<[^>]+>", "", str(title_raw)).strip()
            if not title:
                return None

            date_key = field_map.get("date", "start_date")
            date_str = str(item.get(date_key, "")).strip()
            if not date_str:
                return None
            date = self._parse_flexible_datetime(date_str)
            if not date:
                return None

            end_key = field_map.get("end_time", "end_date")
            end_str = str(item.get(end_key, "")).strip()
            end_time: Optional[datetime] = None
            if end_str:
                end_time = self._parse_flexible_datetime(end_str)

            desc_key = field_map.get("description", "description")
            desc_raw = str(item.get(desc_key, "")).strip()
            description: Optional[str] = (
                re.sub(r"<[^>]+>", "", desc_raw).strip() or None
            )

            return Event(
                venue_key=self.venue.key,
                venue_name=self.venue.name,
                title=title,
                date=date,
                start_time=date,
                end_time=end_time,
                description=description,
                extraction_method="api",
            )
        except Exception as e:
            self.logger.debug(f"Error mapping WP item: {e}")
            return None

    def _parse_flexible_datetime(self, text: str) -> Optional[datetime]:
        """Parse ISO 8601 or WordPress local datetime strings."""
        text = text.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
        # WordPress local format: "2025-07-04 18:00:00"
        try:
            return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            self.logger.debug(f"Could not parse datetime: {text!r}")
            return None

    async def _resolve_category_slug(
        self, session: aiohttp.ClientSession, base_url: str, slug: str
    ) -> Optional[int]:
        """Resolve a category slug to its numeric ID via the WP categories API."""
        url = f"{base_url}/wp-json/wp/v2/categories"
        params = {"slug": slug, "per_page": 1}
        try:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                cats = await response.json(content_type=None)
                if cats and isinstance(cats, list):
                    return int(cats[0]["id"])
        except Exception as e:
            self.logger.warning(f"Failed to resolve category slug '{slug}': {e}")
        return None
