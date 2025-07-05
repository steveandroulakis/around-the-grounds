from typing import Dict, Type
from .base import BaseParser
from .stoup_ballard import StoupBallardParser
from .bale_breaker import BaleBreakerParser


class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        'stoup-ballard': StoupBallardParser,
        'yonder-balebreaker': BaleBreakerParser,
    }
    
    @classmethod
    def get_parser(cls, key: str) -> Type[BaseParser]:
        if key not in cls._parsers:
            raise ValueError(f"No parser found for key: {key}")
        return cls._parsers[key]
    
    @classmethod
    def register_parser(cls, key: str, parser_class: Type[BaseParser]) -> None:
        cls._parsers[key] = parser_class
    
    @classmethod
    def get_supported_keys(cls) -> list:
        return list(cls._parsers.keys())