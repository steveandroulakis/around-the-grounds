import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import aiohttp

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

from ..models import Venue, Event
from ..parsers import ParserRegistry


class ScrapingError:
    """Represents an error that occurred during scraping."""

    def __init__(
        self,
        venue: Venue,
        error_type: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        self.venue = venue
        self.error_type = error_type
        self.message = message
        self.details = details
        self.timestamp = datetime.now()

    def __str__(self) -> str:
        return f"{self.error_type}: {self.message}"

    def to_user_message(self) -> str:
        """Create a user-facing summary of the scraping failure."""
        return f"Failed to fetch information for: {self.venue.name}"


class ScraperCoordinator:
    def __init__(
        self, max_concurrent: int = 5, timeout: int = 60, max_retries: int = 3
    ):
        self.max_concurrent = max_concurrent
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.errors: List[ScrapingError] = []

    async def scrape_all(
        self,
        venues: List[Venue],
        timezone: str = "America/Los_Angeles",
    ) -> List[Event]:
        """
        Scrape all venues concurrently and return aggregated events.
        Returns events and stores errors for later reporting.
        """
        self.errors = []  # Reset errors for this run
        self._timezone = timezone

        # Build venue order mapping from config list order so that events
        # within the same day are sorted by the venue's position in the
        # site config, matching the reference site's display order.
        venue_order: Dict[str, int] = {
            v.key: idx for idx, v in enumerate(venues)
        }

        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={"User-Agent": "Around-the-Grounds Event Scraper"},
        ) as session:
            tasks = []
            for venue in venues:
                task = self._scrape_venue(session, venue)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Aggregate results
            all_events: List[Event] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    error = ScrapingError(
                        venue=venues[i],
                        error_type="Unexpected Error",
                        message=f"Unexpected error: {str(result)}",
                        details=str(result),
                    )
                    self.errors.append(error)
                    self.logger.error(
                        f"Unexpected error scraping {venues[i].name}: {result}"
                    )
                    continue

                assert isinstance(
                    result, tuple
                ), "Result should be a tuple from _scrape_venue"
                events: List[Event]
                error_opt: Optional[ScrapingError]
                events, error_opt = result
                if error_opt:
                    self.errors.append(error_opt)
                all_events.extend(events)

        # Filter to next 7 days and sort by date, preserving venue config order
        return self._filter_and_sort_events(all_events, venue_order)

    async def scrape_one(
        self, venue: Venue, timezone: str = "America/Los_Angeles"
    ) -> Tuple[List[Event], Optional[ScrapingError]]:
        """Scrape a single venue using an isolated HTTP session."""
        self._timezone = timezone
        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(
            connector=connector,
            timeout=self.timeout,
            headers={"User-Agent": "Around-the-Grounds Event Scraper"},
        ) as session:
            events, error = await self._scrape_venue(session, venue)

        filtered_events = self._filter_and_sort_events(events)
        self.errors = [error] if error else []
        return filtered_events, error

    async def _scrape_venue(
        self, session: aiohttp.ClientSession, venue: Venue
    ) -> Tuple[List[Event], Optional[ScrapingError]]:
        """Scrape a single venue with comprehensive error handling and retry logic."""
        try:
            parser_class = ParserRegistry.get_parser(venue)
            parser = parser_class(venue)
        except (KeyError, ValueError) as e:
            error = ScrapingError(
                venue=venue,
                error_type="Configuration Error",
                message=f"Parser not found for venue key: {venue.key}",
                details=str(e),
            )
            self.logger.error(f"Configuration error for {venue.name}: {str(e)}")
            return [], error

        for attempt in range(self.max_retries):
            try:
                self.logger.info(
                    f"Scraping {venue.name} (attempt {attempt + 1}/{self.max_retries})..."
                )
                events = await parser.parse(session)
                self.logger.info(f"Found {len(events)} events for {venue.name}")

                # Warn about events missing start_time unless venue opts out
                config = venue.parser_config or {}
                if not config.get("times_optional", False):
                    no_time = [e for e in events if e.start_time is None]
                    if no_time:
                        self.logger.warning(
                            f"{len(no_time)}/{len(events)} events from "
                            f"{venue.name} are missing start_time"
                        )

                return events, None

            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                error_msg = f"Connection timeout after {self.timeout.total}s"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Network Timeout",
                        message=error_msg,
                        details=f"Failed after {self.max_retries} attempts",
                    )
                    self.logger.error(f"Timeout scraping {venue.name}: {error_msg}")
                    return [], error
                wait_time = 2**attempt
                self.logger.warning(
                    f"Timeout scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except aiohttp.ClientError as e:
                error_msg = f"Network error: {str(e)}"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Network Error",
                        message=error_msg,
                        details=f"Failed after {self.max_retries} attempts",
                    )
                    self.logger.error(
                        f"Network error scraping {venue.name}: {error_msg}"
                    )
                    return [], error
                wait_time = 2**attempt
                self.logger.warning(
                    f"Network error scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except ValueError as e:
                error = ScrapingError(
                    venue=venue,
                    error_type="Parser Error",
                    message=f"Parsing failed: {str(e)}",
                    details=str(e),
                )
                self.logger.error(f"Parser error for {venue.name}: {str(e)}")
                return [], error

            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                if attempt == self.max_retries - 1:
                    error = ScrapingError(
                        venue=venue,
                        error_type="Unexpected Error",
                        message=error_msg,
                        details=str(e),
                    )
                    self.logger.error(
                        f"Unknown error scraping {venue.name}: {error_msg}"
                    )
                    return [], error
                wait_time = 2**attempt
                self.logger.warning(
                    f"Unknown error scraping {venue.name}, retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

        return [], None

    def _filter_and_sort_events(
        self,
        events: List[Event],
        venue_order: Optional[Dict[str, int]] = None,
    ) -> List[Event]:
        """
        Filter events to next 7 days and sort by (date, venue config order, start_time).
        Uses the site timezone to ensure events are filtered correctly.
        Within each day, events are ordered by the venue's position in the site
        config file, matching the reference site's display order.
        """
        tz_name = getattr(self, "_timezone", "America/Los_Angeles")
        try:
            site_tz = ZoneInfo(tz_name)
        except Exception:
            site_tz = ZoneInfo("America/Los_Angeles")

        now = datetime.now(site_tz)
        one_week_later = now + timedelta(days=7)

        filtered_events = [
            event
            for event in events
            if now.date() <= event.date.date() <= one_week_later.date()
        ]

        # Default venue_order: sort alphabetically by venue_key when no
        # config order is provided (e.g. scrape_one).
        _venue_order = venue_order or {}

        # Normalize to naive datetimes for sorting to avoid TypeError when
        # mixing timezone-aware (e.g. JSON-LD, dateutil) and naive dates.
        def _sort_key(ev: Event) -> tuple:
            d = ev.date.replace(tzinfo=None)
            v = _venue_order.get(ev.venue_key, 999)
            st = ev.start_time.replace(tzinfo=None) if ev.start_time else d
            return (d, v, st)

        filtered_events.sort(key=_sort_key)

        return filtered_events

    def get_errors(self) -> List[ScrapingError]:
        """Get list of errors that occurred during scraping."""
        return self.errors

    def has_errors(self) -> bool:
        """Check if any errors occurred during scraping."""
        return len(self.errors) > 0
