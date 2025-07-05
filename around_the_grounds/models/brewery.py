from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class Brewery:
    key: str
    name: str
    url: str
    parser_config: Optional[Dict[str, Any]] = None
    
    def __post_init__(self) -> None:
        if self.parser_config is None:
            self.parser_config = {}