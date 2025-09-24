from typing import Dict, Type

from .base import BaseParser
from .api_based import SquarespaceCalendarParser, HiveyApiParser, SeattleFoodTruckApiParser
from .document_based import GoogleSheetsCsvParser
from .html_based import HtmlSelectorsParser, RegexTextParser, TextSearchHtmlParser


class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        # Technology-based parser keys
        "squarespace_calendar": SquarespaceCalendarParser,
        "hivey_api": HiveyApiParser,
        "seattle_food_truck_api": SeattleFoodTruckApiParser,
        "google_sheets_csv": GoogleSheetsCsvParser,
        "html_selectors": HtmlSelectorsParser,
        "regex_text": RegexTextParser,
        "text_search_html": TextSearchHtmlParser,

        # Legacy brewery-specific keys (for backwards compatibility)
        "stoup-ballard": HtmlSelectorsParser,
        "yonder-balebreaker": SquarespaceCalendarParser,
        "obec-brewing": RegexTextParser,
        "urban-family": HiveyApiParser,
        "wheelie-pop": TextSearchHtmlParser,
        "chucks-greenwood": GoogleSheetsCsvParser,
        "salehs-corner": SeattleFoodTruckApiParser,
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
