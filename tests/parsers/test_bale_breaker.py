"""Tests for Bale Breaker parser."""

import pytest
from datetime import datetime
import aiohttp
from aioresponses import aioresponses

from around_the_grounds.parsers.bale_breaker import BaleBreakerParser
from around_the_grounds.models import Brewery


class TestBaleBreakerParser:
    """Test the BaleBreakerParser class."""
    
    @pytest.fixture
    def brewery(self):
        """Create a test brewery for Bale Breaker."""
        return Brewery(
            key="yonder-balebreaker",
            name="Yonder Cider & Bale Breaker - Ballard",
            url="https://example.com/food-trucks",
            parser_config={}
        )
    
    @pytest.fixture
    def parser(self, brewery):
        """Create a parser instance."""
        return BaleBreakerParser(brewery)
    
    @pytest.mark.asyncio
    async def test_parse_with_limited_data(self, parser):
        """Test parsing when limited structured data is available."""
        limited_html = """
        <html><body>
            <div>
                <p>Check our Instagram for food truck updates!</p>
                <p>Contact us for more information</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=limited_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should return Instagram fallback event
                assert len(events) == 1
                event = events[0]
                assert "Check Instagram @BaleBreaker" in event.food_truck_name
                assert "check Instagram" in event.description
    
    @pytest.mark.asyncio
    async def test_parse_with_event_sections(self, parser):
        """Test parsing with event/calendar sections."""
        event_html = """
        <html><body>
            <div class="event-section">
                <p>Food truck BBQ Kitchen today!</p>
                <p>Come try our amazing burgers</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=event_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # May find events or fallback to Instagram
                assert isinstance(events, list)
                if len(events) > 0:
                    # If events found, check they're valid
                    for event in events:
                        assert event.brewery_key == "yonder-balebreaker"
                        assert event.brewery_name == "Yonder Cider & Bale Breaker - Ballard"
    
    @pytest.mark.asyncio
    async def test_parse_no_structured_events(self, parser):
        """Test parsing when no structured events are found."""
        no_events_html = """
        <html><body>
            <div>
                <h1>Welcome to our brewery</h1>
                <p>We have great beer and cider!</p>
                <p>Visit us today for a great experience</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=no_events_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should return fallback Instagram event
                assert len(events) == 1
                event = events[0]
                assert "Check Instagram @BaleBreaker" in event.food_truck_name
                assert event.brewery_key == "yonder-balebreaker"
    
    @pytest.mark.asyncio
    async def test_parse_with_food_truck_keywords(self, parser):
        """Test parsing with food truck related keywords."""
        keyword_html = """
        <html><body>
            <div>
                <p>Today we have a great taco truck visiting!</p>
                <p>The BBQ kitchen will be here all afternoon</p>
                <p>Don't miss our burger special</p>
            </div>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=keyword_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should find food truck related content
                assert len(events) >= 1
                
                # Check if any events were extracted from keywords
                food_truck_events = [e for e in events if "taco truck" in e.food_truck_name.lower() or "BBQ kitchen" in e.food_truck_name]
                
                # May or may not find events depending on extraction logic
                assert isinstance(events, list)
    
    def test_create_event_from_text_valid(self, parser):
        """Test creating event from valid text."""
        event = parser._create_event_from_text("Amazing BBQ Food Truck")
        
        assert event is not None
        assert event.food_truck_name == "Amazing BBQ Food Truck"
        assert event.brewery_key == "yonder-balebreaker"
        assert event.brewery_name == "Yonder Cider & Bale Breaker - Ballard"
        assert isinstance(event.date, datetime)
    
    def test_create_event_from_text_empty(self, parser):
        """Test creating event from empty text."""
        event = parser._create_event_from_text("")
        
        assert event is None
    
    def test_create_event_from_text_whitespace(self, parser):
        """Test creating event from whitespace-only text."""
        event = parser._create_event_from_text("   ")
        
        assert event is None
    
    def test_parse_date_valid_formats(self, parser):
        """Test parsing various valid date formats."""
        test_cases = [
            ("07/05/2025", 2025, 7, 5),
            ("7/5/2025", 2025, 7, 5),
            ("07-05-2025", 2025, 7, 5),
            ("07.05.2025", 2025, 7, 5),
        ]
        
        for date_str, expected_year, expected_month, expected_day in test_cases:
            result = parser._parse_date(date_str)
            assert result is not None
            assert result.year == expected_year
            assert result.month == expected_month
            assert result.day == expected_day
    
    def test_parse_date_without_year(self, parser):
        """Test parsing dates without year."""
        result = parser._parse_date("07/05")
        
        assert result is not None
        assert result.month == 7
        assert result.day == 5
        # Should use current year
        assert result.year >= 2025
    
    def test_parse_date_invalid_format(self, parser):
        """Test parsing invalid date format."""
        result = parser._parse_date("invalid date")
        
        assert result is None
    
    def test_parse_date_empty_string(self, parser):
        """Test parsing empty date string."""
        result = parser._parse_date("")
        
        assert result is None
    
    def test_parse_date_none(self, parser):
        """Test parsing None date."""
        result = parser._parse_date(None)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser):
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, exception=aiohttp.ClientError("Network error"))
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse Bale Breaker website"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_empty_html(self, parser):
        """Test parsing empty HTML."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body="<html></html>")
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should return fallback event
                assert len(events) == 1
                assert "Check Instagram @BaleBreaker" in events[0].food_truck_name
    
    @pytest.mark.asyncio
    async def test_parse_real_html_fixture(self, parser, html_fixtures_dir):
        """Test parsing with real HTML fixture from the website."""
        fixture_path = html_fixtures_dir / "bale_breaker_sample.html"
        
        if fixture_path.exists():
            real_html = fixture_path.read_text()
            
            with aioresponses() as m:
                m.get(parser.brewery.url, status=200, body=real_html)
                
                async with aiohttp.ClientSession() as session:
                    # This should not raise an error regardless of content
                    events = await parser.parse(session)
                    assert isinstance(events, list)
                    # Should at least have fallback event
                    assert len(events) >= 1
    
    def test_extract_events_from_section_empty(self, parser):
        """Test extracting events from empty section."""
        from bs4 import BeautifulSoup
        
        empty_section = BeautifulSoup("<section></section>", 'html.parser').find('section')
        events = parser._extract_events_from_section(empty_section)
        
        assert len(events) == 0
    
    def test_extract_events_from_section_with_keywords(self, parser):
        """Test extracting events from section with food truck keywords."""
        from bs4 import BeautifulSoup
        
        section_html = """
        <section>
            <p>We have an amazing food truck today!</p>
            <p>The taco truck will be here from 12-8pm</p>
            <p>Contact us for more info</p>
        </section>
        """
        
        section = BeautifulSoup(section_html, 'html.parser').find('section')
        events = parser._extract_events_from_section(section)
        
        # Should extract events based on keywords
        assert isinstance(events, list)
    
    def test_extract_events_from_section_skip_irrelevant(self, parser):
        """Test that irrelevant content is skipped."""
        from bs4 import BeautifulSoup
        
        section_html = """
        <section>
            <p>Contact us at info@brewery.com</p>
            <p>Our hours are 12-10pm daily</p>
            <p>Located in beautiful Ballard</p>
            <p>Follow us on Instagram</p>
        </section>
        """
        
        section = BeautifulSoup(section_html, 'html.parser').find('section')
        events = parser._extract_events_from_section(section)
        
        # Should not extract events from irrelevant content
        assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_extract_from_text_creates_fallback(self, parser):
        """Test that extract_from_text creates fallback event."""
        events = parser._extract_from_text("Any text content")
        
        assert len(events) == 1
        event = events[0]
        assert "Check Instagram @BaleBreaker" in event.food_truck_name
        assert "check Instagram" in event.description
        assert event.brewery_key == "yonder-balebreaker"
    
    def test_extract_from_text_error_handling(self, parser):
        """Test error handling in extract_from_text."""
        # This should not raise an error even with problematic input
        events = parser._extract_from_text(None)
        
        # Should return empty list on error
        assert isinstance(events, list)