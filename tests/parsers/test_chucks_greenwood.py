"""Tests for Chuck's Greenwood parser."""

from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from around_the_grounds.models import Brewery
from around_the_grounds.parsers.chucks_greenwood import ChucksGreenwoodParser


class TestChucksGreenwoodParser:
    """Test the ChucksGreenwoodParser class."""

    @pytest.fixture
    def brewery(self) -> Brewery:
        """Create a test brewery for Chuck's Greenwood."""
        return Brewery(
            key="chucks-greenwood",
            name="Chuck's Hop Shop Greenwood",
            url="https://docs.google.com/spreadsheets/d/e/2PACX-1vS8BmXLSrsUVJ1x_x8FslWooOXRLeEJV-Jq5NzhfUCI9TtO-qXr0ey2BzY8KI-GflT7ekl5015XX3uj/pub?gid=1143085558&single=true&output=csv",
            parser_config={
                "note": "Google Sheets CSV export with automatic monthly updates",
                "csv_direct": True,
                "event_type_filter": "Food Truck",
            },
        )

    @pytest.fixture
    def parser(self, brewery: Brewery) -> ChucksGreenwoodParser:
        """Create a parser instance."""
        return ChucksGreenwoodParser(brewery)

    @pytest.fixture
    def sample_csv(self, csv_fixtures_dir: Path) -> str:
        """Load sample CSV fixture."""
        fixture_path = csv_fixtures_dir / "chucks_greenwood_sample.csv"
        return fixture_path.read_text()

    @pytest.fixture
    def sample_html(self, html_fixtures_dir: Path) -> str:
        """Load sample HTML fixture."""
        fixture_path = html_fixtures_dir / "chucks_greenwood_sample.html"
        return fixture_path.read_text()

    # SUCCESS CASES

    @pytest.mark.asyncio
    @freeze_time("2025-08-05")  # Use consistent test date
    async def test_parse_sample_csv_data(
        self, parser: ChucksGreenwoodParser, sample_csv: str
    ) -> None:
        """Test parsing the sample CSV data."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Validate results
                assert len(events) > 0
                assert all(event.brewery_key == "chucks-greenwood" for event in events)
                assert all(
                    event.brewery_name == "Chuck's Hop Shop Greenwood"
                    for event in events
                )
                assert all(event.food_truck_name.strip() != "" for event in events)
                assert all(event.date is not None for event in events)

                # Check specific events from sample data
                event_names = [event.food_truck_name for event in events]
                assert "T'Juana" in event_names  # From "Dinner: T'Juana"
                assert (
                    "Good Morning Tacos" in event_names
                )  # From "Brunch: Good Morning Tacos"
                assert "Tat's Deli" in event_names  # No prefix

                # Verify events are only food trucks (no "Geeks Who Drink Trivia" or "Music Bingo")
                for event in events:
                    assert "Trivia" not in event.food_truck_name
                    assert "Bingo" not in event.food_truck_name

    @pytest.mark.asyncio
    @freeze_time("2025-08-05")
    async def test_parse_with_redirect(
        self, parser: ChucksGreenwoodParser, sample_csv: str
    ) -> None:
        """Test parsing with Google CDN redirect."""
        redirect_url = "https://doc-0s-3s-sheets.googleusercontent.com/pub/example/csv"

        with aioresponses() as m:
            # Mock redirect from original URL to CDN
            m.get(parser.brewery.url, status=307, headers={"Location": redirect_url})
            m.get(redirect_url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) > 0

    # ERROR HANDLING TESTS

    @pytest.mark.asyncio
    async def test_parse_empty_csv(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing when CSV is empty."""
        empty_csv = ""

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=empty_csv)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_header_only_csv(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing when CSV has only headers."""
        header_only_csv = "Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event"

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=header_only_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_no_food_truck_events(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing when no food truck entries are found."""
        non_food_truck_csv = """Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event
Wed,Aug 6,12 AM,to,Wed,Event,Geeks Who Drink Trivia,Thu,Wed,FALSE,TRUE
Tue,Aug 12,12 AM,to,Tue,Event,Music Bingo,Wed,Tue,FALSE,TRUE"""

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=non_food_truck_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_error(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of HTTP errors."""
        with aioresponses() as m:
            m.get(parser.brewery.url, status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_malformed_csv(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of malformed CSV data."""
        malformed_csv = """Incomplete row,missing,columns
Another,incomplete"""

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=malformed_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                # Should handle gracefully and return empty list
                assert len(events) == 0

    # VENDOR NAME EXTRACTION TESTS

    def test_extract_vendor_name_with_dinner_prefix(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction with dinner prefix."""
        result = parser._extract_vendor_name("Dinner: T'Juana")
        assert result == "T'Juana"

    def test_extract_vendor_name_with_brunch_prefix(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction with brunch prefix."""
        result = parser._extract_vendor_name("Brunch: Good Morning Tacos")
        assert result == "Good Morning Tacos"

    def test_extract_vendor_name_without_prefix(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction without meal prefix."""
        result = parser._extract_vendor_name("Tat's Deli")
        assert result == "Tat's Deli"

    def test_extract_vendor_name_with_unknown_prefix(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction with unknown prefix."""
        result = parser._extract_vendor_name("Lunch: Some Vendor")
        assert result == "Lunch: Some Vendor"  # Should return whole string

    def test_extract_vendor_name_empty_after_colon(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction when empty after colon."""
        result = parser._extract_vendor_name("Dinner: ")
        assert result is None

    def test_extract_vendor_name_empty_input(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction with empty input."""
        result = parser._extract_vendor_name("")
        assert result is None

    def test_extract_vendor_name_whitespace_only(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test vendor name extraction with whitespace only."""
        result = parser._extract_vendor_name("   ")
        assert result is None

    # DATE PARSING TESTS

    @freeze_time("2025-08-05")
    def test_parse_date_current_year(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing for current year."""
        result = parser._parse_date_from_month_date_column("Fri", "Aug 15")
        assert result is not None
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 15

    @freeze_time("2025-12-25")
    def test_parse_date_next_year_rollover(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing with year rollover."""
        result = parser._parse_date_from_month_date_column("Wed", "Jan 15")
        assert result is not None
        assert result.year == 2026  # Should be next year
        assert result.month == 1
        assert result.day == 15

    @freeze_time("2025-08-05")
    def test_parse_date_same_month(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing for same month."""
        result = parser._parse_date_from_month_date_column("Sun", "Aug 10")
        assert result is not None
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 10

    def test_parse_date_invalid_month(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing with invalid month."""
        result = parser._parse_date_from_month_date_column("Mon", "InvalidMonth 15")
        assert result is None

    def test_parse_date_invalid_day(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing with invalid day."""
        result = parser._parse_date_from_month_date_column("Tue", "Aug invalid")
        assert result is None

    def test_parse_date_out_of_range_day(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing with out of range day."""
        result = parser._parse_date_from_month_date_column("Wed", "Aug 32")
        assert result is None

    def test_parse_date_empty_inputs(self, parser: ChucksGreenwoodParser) -> None:
        """Test date parsing with empty inputs."""
        result = parser._parse_date_from_month_date_column("", "")
        assert result is None

        result = parser._parse_date_from_month_date_column("Fri", "")
        assert result is None

        result = parser._parse_date_from_month_date_column("Fri", "Aug")
        assert result is None  # Missing day number

    # CSV ROW PARSING TESTS

    @freeze_time("2025-08-05")
    def test_parse_csv_row_valid_food_truck(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing a valid food truck CSV row."""
        row = [
            "Fri",
            "Aug 1",
            "12 AM",
            "to",
            "Sat",
            "Food Truck",
            "Dinner: T'Juana",
            "Wed",
            "Tue",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is not None
        assert result.brewery_key == "chucks-greenwood"
        assert result.brewery_name == "Chuck's Hop Shop Greenwood"
        assert result.food_truck_name == "T'Juana"
        assert result.date.year == 2025
        assert result.date.month == 8
        assert result.date.day == 1
        assert result.description is not None
        assert "Dinner: T'Juana" in result.description

    def test_parse_csv_row_non_food_truck_event(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing a non-food truck event row."""
        row = [
            "Wed",
            "Aug 6",
            "12 AM",
            "to",
            "Wed",
            "Event",
            "Geeks Who Drink Trivia",
            "Thu",
            "Wed",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is None

    def test_parse_csv_row_too_short(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing a CSV row that's too short."""
        row = ["Fri", "Aug 1", "12 AM"]  # Only 3 columns, need at least 7

        result = parser._parse_csv_row(row)
        assert result is None

    def test_parse_csv_row_empty_row(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing an empty CSV row."""
        row = ["", "", "", "", "", "", "", ""]

        result = parser._parse_csv_row(row)
        assert result is None

    def test_parse_csv_row_empty_event_name(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing a row with empty event name."""
        row = [
            "Fri",
            "Aug 1",
            "12 AM",
            "to",
            "Sat",
            "Food Truck",
            "",
            "Wed",
            "Tue",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is None

    def test_parse_csv_row_invalid_date(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing a row with invalid date."""
        row = [
            "Fri",
            "InvalidMonth 1",
            "12 AM",
            "to",
            "Sat",
            "Food Truck",
            "Test Vendor",
            "Wed",
            "Tue",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is None

    # VALIDATION TESTS

    def test_parse_invalid_formats(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing with various invalid data formats."""
        invalid_inputs = [
            "",  # Empty string
            "   ",  # Whitespace only
            "Invalid format",  # Doesn't match expected pattern
            "Dinner:",  # Empty after colon
            ":",  # Just colon
        ]

        for invalid_input in invalid_inputs:
            result = parser._extract_vendor_name(invalid_input)
            if invalid_input.strip():
                # Non-empty strings should return something or None
                assert result is None or isinstance(result, str)
            else:
                # Empty/whitespace strings should return None
                assert result is None

    @pytest.mark.asyncio
    async def test_parse_real_html_fixture(
        self, parser: ChucksGreenwoodParser, sample_html: str
    ) -> None:
        """Test parsing with real HTML fixture from the website."""
        # Note: This HTML fixture represents the Google Sheets redirect page
        # In practice, the CSV URL redirects to actual CSV data
        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=sample_html)

            async with aiohttp.ClientSession() as session:
                # HTML content will be parsed as CSV but won't contain valid food truck events
                events = await parser.parse(session)
                assert len(events) == 0  # No valid food truck events found in HTML

    # INTEGRATION TESTS

    @pytest.mark.asyncio
    @freeze_time("2025-08-05")
    async def test_parse_mixed_event_types(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing CSV with mixed food truck and non-food truck events."""
        mixed_csv = """Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event
Fri,Aug 1,12 AM,to,Sat,Food Truck,Dinner: T'Juana,Wed,Tue,FALSE,TRUE
Sat,Aug 2,12 AM,to,Thu,Event,Trivia Night,Tue,Sat,FALSE,TRUE
Sun,Aug 3,12 AM,to,Sun,Food Truck,Brunch: Good Morning Tacos,Wed,Sun,FALSE,TRUE
Mon,Aug 4,12 AM,to,Mon,Event,Music Bingo,Sun,Mon,FALSE,TRUE
Tue,Aug 5,12 AM,to,Tue,Food Truck,Tat's Deli,Wed,Tue,FALSE,TRUE"""

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=mixed_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should only have food truck events
                assert len(events) == 3
                event_names = [event.food_truck_name for event in events]
                assert "T'Juana" in event_names
                assert "Good Morning Tacos" in event_names
                assert "Tat's Deli" in event_names

                # Should not have trivia or bingo events
                for event in events:
                    assert "Trivia" not in event.food_truck_name
                    assert "Bingo" not in event.food_truck_name

    @pytest.mark.asyncio
    @freeze_time("2025-12-15")  # Test year rollover scenario
    async def test_parse_year_rollover_dates(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing dates that should be in next year."""
        rollover_csv = """Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event
Mon,Jan 15,12 AM,to,Mon,Food Truck,New Year Vendor,Sat,Mon,FALSE,TRUE
Tue,Feb 20,12 AM,to,Tue,Food Truck,February Truck,Sun,Tue,FALSE,TRUE"""

        with aioresponses() as m:
            m.get(parser.brewery.url, status=200, body=rollover_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) == 2
                # All events should be in 2026 (next year from test date 2025-12-15)
                for event in events:
                    assert event.date.year == 2026
