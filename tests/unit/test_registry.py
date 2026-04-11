"""Unit tests for parser registry."""

import pytest

from around_the_grounds.models import Venue
from around_the_grounds.parsers.bale_breaker import BaleBreakerParser
from around_the_grounds.parsers.base import BaseParser
from around_the_grounds.parsers.generic import AjaxParser, HtmlSelectorParser, WordPressParser
from around_the_grounds.parsers.registry import ParserRegistry
from around_the_grounds.parsers.stoup_ballard import StoupBallardParser


def _venue(key: str, source_type: str = "html") -> Venue:
    return Venue(key=key, name=key, url="https://example.com", source_type=source_type)


class TestParserRegistry:
    """Test the ParserRegistry class."""

    def test_get_existing_parser(self) -> None:
        """Test getting an existing specific parser by venue.key."""
        parser_class = ParserRegistry.get_parser(_venue("stoup-ballard"))
        assert parser_class == StoupBallardParser

        parser_class = ParserRegistry.get_parser(_venue("yonder-balebreaker"))
        assert parser_class == BaleBreakerParser

    def test_get_generic_parser_wordpress(self) -> None:
        """Test that an unknown key falls back to generic wordpress parser."""
        parser_class = ParserRegistry.get_parser(_venue("some-new-site", "wordpress"))
        assert parser_class == WordPressParser

    def test_get_generic_parser_html(self) -> None:
        """Test that an unknown key falls back to generic html parser."""
        parser_class = ParserRegistry.get_parser(_venue("some-new-site", "html"))
        assert parser_class == HtmlSelectorParser

    def test_get_generic_parser_ajax(self) -> None:
        """Test that an unknown key falls back to generic ajax parser."""
        parser_class = ParserRegistry.get_parser(_venue("some-new-site", "ajax"))
        assert parser_class == AjaxParser

    def test_specific_parser_takes_precedence(self) -> None:
        """Specific parsers win over generic when venue.key matches."""
        # stoup-ballard has source_type "html" but its specific parser should win
        venue = Venue(key="stoup-ballard", name="Stoup", url="https://example.com", source_type="html")
        parser_class = ParserRegistry.get_parser(venue)
        assert parser_class == StoupBallardParser

    def test_get_nonexistent_parser(self) -> None:
        """Test getting a parser for unknown key AND unknown source_type raises."""
        with pytest.raises(ValueError):
            ParserRegistry.get_parser(_venue("nonexistent-parser", "unknown-type"))

    def test_get_supported_keys(self) -> None:
        """Test getting all supported specific parser keys."""
        keys = ParserRegistry.get_supported_keys()

        assert "stoup-ballard" in keys
        assert "yonder-balebreaker" in keys
        assert isinstance(keys, list)

    def test_parser_registry_is_not_empty(self) -> None:
        """Test that the parser registry is not empty."""
        keys = ParserRegistry.get_supported_keys()
        assert len(keys) > 0

    def test_parsers_are_classes(self) -> None:
        """Test that registered specific parsers are actually classes."""
        keys = ParserRegistry.get_supported_keys()

        for key in keys:
            parser_class = ParserRegistry.get_parser(_venue(key))
            assert callable(parser_class)
            # Check that it's a class (has __name__ attribute)
            assert hasattr(parser_class, "__name__")

    def test_register_parser(self) -> None:
        """Test registering a new parser."""

        # Create a dummy parser class
        class DummyParser(BaseParser):
            async def parse(self, session):  # type: ignore
                return []

        # Register it
        ParserRegistry.register_parser("dummy", DummyParser)

        # Verify it was registered
        assert "dummy" in ParserRegistry.get_supported_keys()
        assert ParserRegistry.get_parser(_venue("dummy")) == DummyParser

        # Clean up - remove the dummy parser
        ParserRegistry._specific.pop("dummy", None)

    def test_case_sensitive_parser_keys(self) -> None:
        """Test that parser keys are case sensitive."""
        # Should work with correct case
        parser_class = ParserRegistry.get_parser(_venue("stoup-ballard"))
        assert parser_class == StoupBallardParser

        # Should fail with incorrect case (and unknown source_type)
        with pytest.raises(ValueError):
            ParserRegistry.get_parser(_venue("Stoup-Ballard", "unknown"))

        with pytest.raises(ValueError):
            ParserRegistry.get_parser(_venue("STOUP-BALLARD", "unknown"))
