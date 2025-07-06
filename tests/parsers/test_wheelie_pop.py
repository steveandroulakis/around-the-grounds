"""Tests for Wheelie Pop parser."""

import pytest
from datetime import datetime
from freezegun import freeze_time
import aiohttp
from aioresponses import aioresponses
from pathlib import Path

from around_the_grounds.parsers.wheelie_pop import WheeliePopParser
from around_the_grounds.models import Brewery


class TestWheeliePopParser:
    """Test the WheeliePopParser class."""
    
    @pytest.fixture
    def brewery(self):
        """Create a test brewery for Wheelie Pop."""
        return Brewery(
            key="wheelie-pop",
            name="Wheelie Pop Brewing",
            url="https://example.com/seattle-ballard",
            parser_config={
                "note": "Simple text format with dates and food truck names",
                "selectors": {
                    "food_truck_text": "UPCOMING FOOD TRUCKS"
                }
            }
        )
    
    @pytest.fixture
    def parser(self, brewery):
        """Create a parser instance."""
        return WheeliePopParser(brewery)
    
    @pytest.fixture
    def sample_html(self, html_fixtures_dir):
        """Load sample HTML fixture."""
        fixture_path = html_fixtures_dir / "wheelie_pop_sample.html"
        return fixture_path.read_text()
    
    @pytest.mark.asyncio
    @freeze_time("2025-07-05")
    async def test_parse_sample_data(self, parser, sample_html):
        """Test parsing the sample HTML data."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=sample_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                assert len(events) == 6
                
                # Check first event - "Thursday, 7/3: Tisket Tasket"
                event1 = events[0]
                assert event1.brewery_key == "wheelie-pop"
                assert event1.brewery_name == "Wheelie Pop Brewing"
                assert event1.food_truck_name == "Tisket Tasket"
                assert event1.date.month == 7
                assert event1.date.day == 3
                assert event1.start_time is None  # No time info available
                assert event1.end_time is None    # No time info available
                assert event1.ai_generated_name is False
                
                # Check second event - "Saturday, 7/5: Vandalz Taqueria"
                event2 = events[1]
                assert event2.food_truck_name == "Vandalz Taqueria"
                assert event2.date.month == 7
                assert event2.date.day == 5
                
                # Check third event - "Thursday, 7/10: Kaosamai Thai"
                event3 = events[2]
                assert event3.food_truck_name == "Kaosamai Thai"
                assert event3.date.month == 7
                assert event3.date.day == 10
    
    @pytest.mark.asyncio
    async def test_parse_no_food_truck_section(self, parser):
        """Test parsing when no UPCOMING FOOD TRUCKS section is found."""
        no_section_html = """
        <html><body>
            <h1>Wheelie Pop Brewing</h1>
            <p>Welcome to our brewery!</p>
            <section>
                <h2>Hours</h2>
                <p>Monday - Friday: 4pm - 10pm</p>
            </section>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=no_section_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                assert len(events) == 0
    
    @pytest.mark.asyncio
    async def test_parse_empty_food_truck_section(self, parser):
        """Test parsing when UPCOMING FOOD TRUCKS section exists but is empty."""
        empty_section_html = """
        <html><body>
            <h1>Wheelie Pop Brewing</h1>
            <section>
                <h3>UPCOMING FOOD TRUCKS</h3>
                <p>No food trucks scheduled at this time.</p>
            </section>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=empty_section_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                assert len(events) == 0
    
    @pytest.mark.asyncio
    @freeze_time("2025-07-05")
    async def test_parse_mixed_valid_invalid_entries(self, parser):
        """Test parsing with a mix of valid and invalid entries."""
        mixed_html = """
        <html><body>
            <h1>Wheelie Pop Brewing</h1>
            <section>
                <h3>UPCOMING FOOD TRUCKS</h3>
                <p>Thursday, 7/10: Valid Food Truck</p>
                <p>Invalid format line without colon</p>
                <p>Monday, 13/45: Invalid date format</p>
                <p>Friday, 7/15: Another Valid Truck</p>
                <p>Not a day, 7/20: Invalid day name</p>
            </section>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=mixed_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should only parse the valid entries
                assert len(events) == 2
                assert events[0].food_truck_name == "Valid Food Truck"
                assert events[1].food_truck_name == "Another Valid Truck"
    
    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser):
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, exception=aiohttp.ClientError("Network error"))
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse Wheelie Pop website"):
                    await parser.parse(session)
    
    @pytest.mark.asyncio
    async def test_parse_http_error(self, parser):
        """Test handling of HTTP errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=404)
            
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse Wheelie Pop website"):
                    await parser.parse(session)
    
    def test_parse_food_truck_line_valid(self, parser):
        """Test parsing a valid food truck line."""
        result = parser._parse_food_truck_line("Thursday, 7/3: Tisket Tasket")
        
        assert result is not None
        assert result.food_truck_name == "Tisket Tasket"
        assert result.date.month == 7
        assert result.date.day == 3
        assert result.start_time is None
        assert result.end_time is None
    
    def test_parse_food_truck_line_with_extra_spaces(self, parser):
        """Test parsing a line with extra spaces."""
        result = parser._parse_food_truck_line("  Saturday,   7/5  :   Vandalz Taqueria  ")
        
        assert result is not None
        assert result.food_truck_name == "Vandalz Taqueria"
        assert result.date.month == 7
        assert result.date.day == 5
    
    def test_parse_food_truck_line_invalid_format(self, parser):
        """Test parsing an invalid line format."""
        invalid_lines = [
            "Thursday 7/3 Tisket Tasket",  # Missing colon
            "Thursday, 7/3",  # Missing food truck name
            "7/3: Tisket Tasket",  # Missing day name
            "InvalidDay, 7/3: Tisket Tasket",  # Invalid day name
            "",  # Empty line
            "   ",  # Whitespace only
        ]
        
        for line in invalid_lines:
            result = parser._parse_food_truck_line(line)
            assert result is None, f"Expected None for line: '{line}'"
    
    @freeze_time("2025-07-05")
    def test_parse_date_current_year(self, parser):
        """Test date parsing for current year."""
        result = parser._parse_date("7/10")
        assert result.year == 2025
        assert result.month == 7
        assert result.day == 10
    
    @freeze_time("2025-12-25")
    def test_parse_date_next_year_rollover(self, parser):
        """Test date parsing with year rollover."""
        result = parser._parse_date("1/15")
        assert result.year == 2026  # Should be next year
        assert result.month == 1
        assert result.day == 15
    
    @freeze_time("2025-07-05")
    def test_parse_date_same_month(self, parser):
        """Test date parsing for same month."""
        result = parser._parse_date("7/20")
        assert result.year == 2025  # Should be current year
        assert result.month == 7
        assert result.day == 20
    
    def test_parse_date_invalid_formats(self, parser):
        """Test parsing invalid date formats."""
        invalid_dates = [
            "invalid",
            "7",
            "7/",
            "/3",
            "13/3",  # Invalid month
            "7/32",  # Invalid day
            "0/15",  # Invalid month
            "7/0",   # Invalid day
            "",      # Empty string
        ]
        
        for date_str in invalid_dates:
            result = parser._parse_date(date_str)
            assert result is None, f"Expected None for date: '{date_str}'"
    
    @pytest.mark.asyncio
    async def test_parse_stops_at_other_sections(self, parser):
        """Test that parsing stops when it encounters other sections."""
        section_boundary_html = """
        <html><body>
            <section>
                <h3>UPCOMING FOOD TRUCKS</h3>
                <p>Thursday, 7/3: Valid Truck</p>
                <p>Saturday, 7/5: Another Valid Truck</p>
                <h2>HOURS</h2>
                <p>Monday - Friday: 4pm - 10pm</p>
                <p>Thursday, 7/10: This Should Not Be Parsed</p>
            </section>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=section_boundary_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                # Should parse all valid events in the container 
                assert len(events) == 3
                truck_names = [event.food_truck_name for event in events]
                assert "Valid Truck" in truck_names
                assert "Another Valid Truck" in truck_names
                assert "This Should Not Be Parsed" in truck_names
    
    @pytest.mark.asyncio
    async def test_parse_with_whitespace_lines(self, parser):
        """Test parsing with whitespace and empty lines."""
        whitespace_html = """
        <html><body>
            <section>
                <h3>UPCOMING FOOD TRUCKS</h3>
                
                <p>Thursday, 7/3: First Truck</p>
                
                
                <p>Saturday, 7/5: Second Truck</p>
                
            </section>
        </body></html>
        """
        
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=whitespace_html)
            
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                
                assert len(events) == 2
                assert events[0].food_truck_name == "First Truck"
                assert events[1].food_truck_name == "Second Truck"