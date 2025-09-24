from dataclasses import dataclass
from typing import List, Optional

from .event_source import EventSource


@dataclass
class SiteConfig:
    """
    Configuration for a single website/site.

    Each YAML file represents one SiteConfig which generates one unique website.
    """
    name: str
    template_type: str  # "food_events", "music_events", "family_events", etc.
    website_title: str
    repository_url: str
    description: str
    sources: List[EventSource]
    event_category: Optional[str] = None  # Default category for events from this site

    def __post_init__(self) -> None:
        # Ensure sources is always a list
        if not isinstance(self.sources, list):
            self.sources = []