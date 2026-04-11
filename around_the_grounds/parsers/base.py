import logging
from abc import ABC, abstractmethod
from typing import List

import aiohttp
from bs4 import BeautifulSoup

from ..models import Venue, Event


class BaseParser(ABC):
    def __init__(self, venue: Venue):
        self.venue = venue
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def parse(self, session: aiohttp.ClientSession) -> List[Event]:
        pass

    async def fetch_page(
        self, session: aiohttp.ClientSession, url: str
    ) -> BeautifulSoup:
        """
        Fetch and parse a webpage with error handling.
        """
        try:
            self.logger.debug(f"Fetching page: {url}")
            async with session.get(url) as response:
                if response.status == 404:
                    raise ValueError(f"Page not found (404): {url}")
                elif response.status == 403:
                    raise ValueError(f"Access forbidden (403): {url}")
                elif response.status == 500:
                    raise ValueError(f"Server error (500): {url}")
                elif response.status != 200:
                    raise ValueError(f"HTTP {response.status}: {url}")

                content = await response.text()

                if not content or len(content.strip()) == 0:
                    raise ValueError(f"Empty response from: {url}")

                soup = BeautifulSoup(content, "html.parser")

                # Basic validation that we got HTML
                if not soup.find("html") and not soup.find("body"):
                    self.logger.warning(f"Response doesn't appear to be HTML: {url}")

                return soup

        except aiohttp.ClientError as e:
            raise ValueError(f"Network error fetching {url}: {str(e)}")
        except Exception as e:
            if isinstance(e, ValueError):
                raise  # Re-raise our custom ValueError messages
            raise ValueError(f"Failed to parse HTML from {url}: {str(e)}")

    def validate_event(self, event: Event) -> bool:
        """
        Validate an Event has required fields.
        """
        if not event.venue_key or not event.venue_name:
            self.logger.warning(f"Event missing venue info: {event}")
            return False

        if not event.title or event.title.strip() == "":
            self.logger.warning(f"Event missing title: {event}")
            return False

        if not event.date:
            self.logger.warning(f"Event missing date: {event}")
            return False

        return True

    def filter_valid_events(self, events: List[Event]) -> List[Event]:
        """
        Filter events to only include valid ones.
        """
        valid_events = []
        for event in events:
            if self.validate_event(event):
                valid_events.append(event)
            else:
                self.logger.debug(f"Filtered out invalid event: {event}")

        return valid_events
