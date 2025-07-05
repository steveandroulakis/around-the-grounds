"""Unit tests for parser registry."""

import pytest

from around_the_grounds.parsers.registry import ParserRegistry
from around_the_grounds.parsers.base import BaseParser
from around_the_grounds.parsers.stoup_ballard import StoupBallardParser
from around_the_grounds.parsers.bale_breaker import BaleBreakerParser


class TestParserRegistry:
    """Test the ParserRegistry class."""
    
    def test_get_existing_parser(self):
        """Test getting an existing parser."""
        parser_class = ParserRegistry.get_parser("stoup-ballard")
        assert parser_class == StoupBallardParser
        
        parser_class = ParserRegistry.get_parser("yonder-balebreaker")
        assert parser_class == BaleBreakerParser
    
    def test_get_nonexistent_parser(self):
        """Test getting a parser that doesn't exist."""
        with pytest.raises(ValueError):
            ParserRegistry.get_parser("nonexistent-parser")
    
    def test_get_supported_keys(self):
        """Test getting all supported parser keys."""
        keys = ParserRegistry.get_supported_keys()
        
        assert "stoup-ballard" in keys
        assert "yonder-balebreaker" in keys
        assert isinstance(keys, list)
    
    def test_parser_registry_is_not_empty(self):
        """Test that the parser registry is not empty."""
        keys = ParserRegistry.get_supported_keys()
        assert len(keys) > 0
    
    def test_parsers_are_classes(self):
        """Test that registered parsers are actually classes."""
        keys = ParserRegistry.get_supported_keys()
        
        for key in keys:
            parser_class = ParserRegistry.get_parser(key)
            assert callable(parser_class)
            # Check that it's a class (has __name__ attribute)
            assert hasattr(parser_class, "__name__")
    
    def test_register_parser(self):
        """Test registering a new parser."""
        # Create a dummy parser class
        class DummyParser(BaseParser):
            async def parse(self, session):
                return []
        
        # Register it
        ParserRegistry.register_parser("dummy", DummyParser)
        
        # Verify it was registered
        assert "dummy" in ParserRegistry.get_supported_keys()
        assert ParserRegistry.get_parser("dummy") == DummyParser
        
        # Clean up - remove the dummy parser
        ParserRegistry._parsers.pop("dummy", None)
    
    def test_case_sensitive_parser_keys(self):
        """Test that parser keys are case sensitive."""
        # Should work with correct case
        parser_class = ParserRegistry.get_parser("stoup-ballard")
        assert parser_class == StoupBallardParser
        
        # Should fail with incorrect case
        with pytest.raises(ValueError):
            ParserRegistry.get_parser("Stoup-Ballard")
        
        with pytest.raises(ValueError):
            ParserRegistry.get_parser("STOUP-BALLARD")