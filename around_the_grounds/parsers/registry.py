from typing import Dict, List, Type

from .bale_breaker import BaleBreakerParser
from .base import BaseParser
from .channel_marker import ChannelMarkerParser
from .chucks_greenwood import ChucksGreenwoodParser
from .generic import AjaxParser, HtmlSelectorParser, JsonLdParser, WordPressParser
from .lucky_envelope import LuckyEnvelopeParser
from .obec_brewing import ObecBrewingParser
from .salehs_corner import SalehsCornerParser
from .stoup_ballard import StoupBallardParser
from .urban_family import UrbanFamilyParser
from .wheelie_pop import WheeliePopParser

from ..models import Venue


class ParserRegistry:
    # Generic parsers — selected by venue.source_type
    _generic: Dict[str, Type[BaseParser]] = {
        "wordpress": WordPressParser,
        "html": HtmlSelectorParser,
        "ajax": AjaxParser,
        "json-ld": JsonLdParser,
    }

    # Specific parsers — selected by venue.key (takes precedence over generic)
    _specific: Dict[str, Type[BaseParser]] = {
        "stoup-ballard": StoupBallardParser,
        "yonder-balebreaker": BaleBreakerParser,
        "obec-brewing": ObecBrewingParser,
        "urban-family": UrbanFamilyParser,
        "wheelie-pop": WheeliePopParser,
        "chucks-greenwood": ChucksGreenwoodParser,
        "salehs-corner": SalehsCornerParser,
        "channel-marker": ChannelMarkerParser,
        "lucky-envelope": LuckyEnvelopeParser,
    }

    @classmethod
    def get_parser(cls, venue: Venue) -> Type[BaseParser]:
        """Return the parser class for a venue.

        Specific parsers (keyed by venue.key) take precedence over
        generic parsers (keyed by venue.source_type).
        """
        if venue.key in cls._specific:
            return cls._specific[venue.key]
        if venue.source_type in cls._generic:
            return cls._generic[venue.source_type]
        raise ValueError(
            f"No parser for venue '{venue.key}' (source_type: '{venue.source_type}')"
        )

    @classmethod
    def register_parser(cls, key: str, parser_class: Type[BaseParser]) -> None:
        cls._specific[key] = parser_class

    @classmethod
    def get_supported_keys(cls) -> List[str]:
        return list(cls._specific.keys())
