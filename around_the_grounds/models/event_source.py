from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class EventSource:
    """
    Generalized event source (replaces Brewery for multi-domain support).

    Represents any source of events - brewery, venue, community board, etc.
    Uses technology-based parser types rather than event-theme based.
    """
    key: str
    name: str
    url: str
    parser_type: str  # Technology-based: "squarespace_calendar", "hivey_api", etc.
    parser_config: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.parser_config is None:
            self.parser_config = {}