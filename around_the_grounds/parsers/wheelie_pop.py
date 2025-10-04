import re
from datetime import datetime
from typing import List, Optional, Set, Tuple

import aiohttp
from bs4 import BeautifulSoup
from bs4.element import Tag

from ..models import FoodTruckEvent
from ..utils.timezone_utils import (
    now_in_pacific,
    parse_date_with_pacific_context,
    utc_to_pacific_naive,
)
from .base import BaseParser


class WheeliePopParser(BaseParser):
    """Parser for Wheelie Pop Brewing's My Calendar feed."""

    CALENDAR_ID = "mc-948a6a8e8cd15db324902317a630b853"
    BASE_URL = "https://wheeliepopbrewing.com/ballard-brewery-district-draft/"

    async def parse(self, session: aiohttp.ClientSession) -> List[FoodTruckEvent]:
        events: List[FoodTruckEvent] = []
        seen_event_keys: Set[str] = set()

        current = now_in_pacific()
        for year, month in self._months_to_fetch(current):
            try:
                html = await self._fetch_calendar_month(session, year, month)
            except ValueError as exc:
                self.logger.error(
                    f"Wheelie Pop calendar request failed for {year}-{month:02d}: {exc}"
                )
                continue

            if not html:
                continue

            month_events = self._parse_calendar_html(html, seen_event_keys)
            events.extend(month_events)

        valid_events = self.filter_valid_events(events)
        self.logger.info(
            f"Parsed {len(valid_events)} valid events from {len(events)} total"
        )
        return valid_events

    def _months_to_fetch(self, current: datetime) -> List[Tuple[int, int]]:
        year = current.year
        month = current.month

        next_year, next_month = self._add_month(year, month)
        return [(year, month), (next_year, next_month)]

    @staticmethod
    def _add_month(year: int, month: int) -> Tuple[int, int]:
        if month == 12:
            return year + 1, 1
        return year, month + 1

    async def _fetch_calendar_month(
        self, session: aiohttp.ClientSession, year: int, month: int
    ) -> Optional[str]:
        params = {
            "yr": str(year),
            "month": f"{month:02d}",
            "dy": "",
            "cid": self.CALENDAR_ID,
            "time": "month",
            "format": "list",
        }

        headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "text/html, */*; q=0.01",
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36"
            ),
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "Referer": (
                f"{self.BASE_URL}?yr={year}&month={month:02d}&dy=&cid={self.CALENDAR_ID}"
                "&time=month&format=list"
            ),
        }

        self.logger.debug(
            f"Requesting Wheelie Pop calendar for {year}-{month:02d} with params {params}"
        )

        try:
            async with session.get(
                self.BASE_URL, params=params, headers=headers
            ) as response:
                if response.status != 200:
                    raise ValueError(f"HTTP {response.status}")

                text = await response.text()
                if not text or not text.strip():
                    raise ValueError("Empty response body")

                return text

        except aiohttp.ClientError as exc:
            raise ValueError(f"Network error: {exc}")

    def _parse_calendar_html(
        self, html: str, seen_event_keys: Set[str]
    ) -> List[FoodTruckEvent]:
        soup = BeautifulSoup(html, "html.parser")

        container = soup.find("div", id=self.CALENDAR_ID)
        if not container:
            self.logger.warning("Wheelie Pop calendar container not found in HTML")
            return []

        list_container = container.find("ul", class_="mc-list")
        if not list_container:
            self.logger.debug("Wheelie Pop calendar list view missing")
            return []

        events: List[FoodTruckEvent] = []
        for day_node in list_container.find_all("li"):
            if "mc-events" not in day_node.get("class", []):
                continue
            date = self._parse_date_from_day(day_node)
            if not date:
                continue

            for article in day_node.find_all("article"):
                event = self._parse_food_truck_article(article, date)
                if not event:
                    continue

                event_key = self._event_key(event)
                if event_key in seen_event_keys:
                    continue

                seen_event_keys.add(event_key)
                events.append(event)

        return events

    def _parse_food_truck_article(
        self, article: Tag, date: datetime
    ) -> Optional[FoodTruckEvent]:
        classes = article.get("class", [])
        if "mc_food-truck" not in classes:
            return None

        title_elem = article.find("h3", class_="event-title")
        raw_title = title_elem.get_text(strip=True) if title_elem else ""
        food_truck_name = self._extract_food_truck_name(raw_title)
        if not food_truck_name:
            self.logger.debug("Skipping article with no food truck name")
            return None

        start_time = self._parse_time(article, ".event-time time")
        end_time = self._parse_time(article, ".end-time time")

        return FoodTruckEvent(
            brewery_key=self.brewery.key,
            brewery_name=self.brewery.name,
            food_truck_name=food_truck_name,
            date=date,
            start_time=start_time,
            end_time=end_time,
            ai_generated_name=False,
        )

    def _parse_time(self, article: Tag, selector: str) -> Optional[datetime]:
        time_node = article.select_one(selector)
        if not time_node:
            return None

        datetime_attr = time_node.get("datetime") or time_node.get("content")
        if not datetime_attr:
            return None

        try:
            parsed = datetime.fromisoformat(datetime_attr)
        except ValueError:
            self.logger.debug(f"Could not parse datetime value: {datetime_attr}")
            return None

        return utc_to_pacific_naive(parsed)

    def _parse_date_from_day(self, day_node: Tag) -> Optional[datetime]:
        day_id = day_node.get("id", "")
        match = re.search(r"list-(\d{4})-(\d{2})-(\d{2})", day_id)
        if not match:
            return None

        year, month, day = map(int, match.groups())
        return parse_date_with_pacific_context(year, month, day)

    def _extract_food_truck_name(self, raw_title: str) -> Optional[str]:
        if not raw_title:
            return None

        if "Food Truck:" in raw_title:
            name = raw_title.split("Food Truck:", 1)[1].strip()
            if name:
                return name

        # Fallback: take text after the final colon, if present
        if ":" in raw_title:
            name = raw_title.split(":")[-1].strip()
            if name:
                return name

        return raw_title.strip() or None

    def _event_key(self, event: FoodTruckEvent) -> str:
        start_key = (
            event.start_time.strftime("%Y-%m-%d %H:%M")
            if event.start_time is not None
            else ""
        )
        return f"{event.date.strftime('%Y-%m-%d')}|{start_key}|{event.food_truck_name.lower()}"
