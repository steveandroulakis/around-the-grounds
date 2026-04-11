from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Venue:
    key: str
    name: str
    url: str
    source_type: str = "html"
    parser_config: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.parser_config is None:
            self.parser_config = {}
