"""Tests for Chuck's Greenwood parser."""

from datetime import datetime
from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from around_the_grounds.models import Venue
from around_the_grounds.parsers.chucks_greenwood import ChucksGreenwoodParser


class TestChucksGreenwoodParser:
    """Test the ChucksGreenwoodParser class."""

    @pytest.fixture
    def brewery(self) -> Venue:
        """Create a test brewery for Chuck's Greenwood."""
        return Venue(
            key="chucks-greenwood",
            name="Chuck's Hop Shop Greenwood",
            url="https://docs.google.com/spreadsheets/d/e/2PACX-1vS8BmXLSrsUVJ1x_x8FslWooOXRLeEJV-Jq5NzhfUCI9TtO-qXr0ey2BzY8KI-GflT7ekl5015XX3uj/pub?gid=1258996532&single=true&output=csv",
            parser_config={
                "note": "Google Sheets CSV export, 'Greenwood' tab",
                "csv_direct": True,
                "event_type_filter": "Food Truck",
            },
        )

    @pytest.fixture
    def parser(self, brewery: Venue) -> ChucksGreenwoodParser:
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
    @freeze_time("2026-09-05")  # matches the dates in the CSV fixture
    async def test_parse_sample_csv_data(
        self, parser: ChucksGreenwoodParser, sample_csv: str
    ) -> None:
        """Test parsing the sample CSV data."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Validate results
                assert len(events) > 0
                assert all(event.venue_key == "chucks-greenwood" for event in events)
                assert all(
                    event.venue_name == "Chuck's Hop Shop Greenwood" for event in events
                )
                assert all(event.title.strip() != "" for event in events)
                assert all(event.date is not None for event in events)

                # Check specific events from sample data
                event_names = [event.title for event in events]
                assert "T'Juana" in event_names  # From "Dinner: T'Juana"
                assert (
                    "Good Morning Tacos" in event_names
                )  # From "Brunch: Good Morning Tacos"
                assert "Tat's Deli" in event_names  # No prefix

                # Verify events are only food trucks (no "Geeks Who Drink Trivia" or "Music Bingo")
                for event in events:
                    assert "Trivia" not in event.title
                    assert "Bingo" not in event.title

                # Every row of the "Greenwood" tab carries start/end hours
                assert all(event.start_time is not None for event in events)
                assert all(event.end_time is not None for event in events)

                by_name = {event.title: event for event in events}
                # "9/13/2026,Sep 13,9,to,15,Food Truck,Brunch: Good Morning Tacos"
                brunch = by_name["Good Morning Tacos"]
                assert brunch.start_time == datetime(2026, 9, 13, 9, 0)
                assert brunch.end_time == datetime(2026, 9, 13, 15, 0)
                # "10/2/2026,Oct 2,17,to,21,Food Truck,Dinner: T'Juana"
                dinner = by_name["T'Juana"]
                assert dinner.start_time == datetime(2026, 10, 2, 17, 0)
                assert dinner.end_time == datetime(2026, 10, 2, 21, 0)

    @pytest.mark.asyncio
    @freeze_time("2026-09-05")  # matches the dates in the CSV fixture
    async def test_parse_with_redirect(
        self, parser: ChucksGreenwoodParser, sample_csv: str
    ) -> None:
        """Test parsing with Google CDN redirect."""
        redirect_url = "https://doc-0s-3s-sheets.googleusercontent.com/pub/example/csv"

        with aioresponses() as m:
            # Mock redirect from original URL to CDN
            m.get(parser.venue.url, status=307, headers={"Location": redirect_url})
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
            m.get(parser.venue.url, status=200, body=empty_csv)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_header_only_csv(self, parser: ChucksGreenwoodParser) -> None:
        """Test parsing when CSV has only headers."""
        header_only_csv = "Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event"

        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=header_only_csv)

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
            m.get(parser.venue.url, status=200, body=non_food_truck_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.venue.url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_error(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of HTTP errors."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_malformed_csv(self, parser: ChucksGreenwoodParser) -> None:
        """Test handling of malformed CSV data."""
        malformed_csv = """Incomplete row,missing,columns
Another,incomplete"""

        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=malformed_csv)

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

    def test_extract_vendor_name_spreadsheet_error_value(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Spreadsheet formula errors must not be treated as vendor names."""
        assert parser._extract_vendor_name("#VALUE!") is None
        assert parser._extract_vendor_name("#REF!") is None
        assert parser._extract_vendor_name("#N/A") is None
        # Case-insensitive and whitespace-tolerant
        assert parser._extract_vendor_name("  #value!  ") is None

    def test_extract_vendor_name_error_value_after_prefix(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A meal prefix followed by a spreadsheet error yields no vendor."""
        assert parser._extract_vendor_name("Dinner: #VALUE!") is None

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
        # Jan 15 2026 is a Thursday, and column A agrees
        result = parser._parse_date_from_month_date_column("Thu", "Jan 15")
        assert result is not None
        assert result.year == 2026  # Should be next year
        assert result.month == 1
        assert result.day == 15

    @freeze_time("2026-09-05")
    def test_parse_date_uses_weekday_to_reject_stale_rows(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A prior-year row is dated to its real year, not today's calendar.

        The "Greenwood" tab keeps a block of stale rows below the current
        schedule. Sep 5 is a Saturday in 2026 but was a Friday in 2025, so
        a row reading "Fri, Sep 05" belongs to 2025 — and once dated
        correctly it falls outside the coordinator's window instead of
        duplicating a real event.
        """
        result = parser._parse_date_from_month_date_column("Fri", "Sep 05")
        assert result is not None
        assert result.year == 2025
        assert (result.month, result.day) == (9, 5)

    @freeze_time("2026-09-05")
    def test_parse_date_keeps_current_year_when_weekday_agrees(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A genuine forward row keeps the inferred year."""
        # Nov 1 2026 is a Sunday
        result = parser._parse_date_from_month_date_column("Sun", "Nov 01")
        assert result is not None
        assert result.year == 2026
        assert (result.month, result.day) == (11, 1)

    @freeze_time("2026-09-05")
    def test_parse_date_unrecognized_weekday_keeps_inferred_year(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Column A that is not a weekday leaves the inference untouched."""
        result = parser._parse_date_from_month_date_column("", "Nov 01")
        assert result is not None
        assert result.year == 2026

    @freeze_time("2026-09-05")
    def test_parse_date_impossible_weekday_keeps_inferred_year(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A weekday no nearby year satisfies is treated as sheet sloppiness.

        Better to keep the event on the inferred date than to drop it.
        """
        # Nov 1 is Sun/Sat/Mon across 2026/2025/2027 — never a Wednesday
        result = parser._parse_date_from_month_date_column("Wed", "Nov 01")
        assert result is not None
        assert result.year == 2026

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

    # HOUR COLUMN PARSING TESTS

    def test_parse_hour_column_whole_hour(self, parser: ChucksGreenwoodParser) -> None:
        """The sheet writes bare 24-hour integers."""
        date = datetime(2026, 9, 4)
        assert parser._parse_hour_column("17", date) == datetime(2026, 9, 4, 17, 0)
        assert parser._parse_hour_column("21", date) == datetime(2026, 9, 4, 21, 0)

    def test_parse_hour_column_single_digit(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Brunch rows use a single-digit hour."""
        date = datetime(2026, 9, 6)
        assert parser._parse_hour_column("9", date) == datetime(2026, 9, 6, 9, 0)

    def test_parse_hour_column_midnight(self, parser: ChucksGreenwoodParser) -> None:
        """A literal "0" is a valid hour, unlike the mobile tab's "12 AM"."""
        date = datetime(2026, 9, 4)
        assert parser._parse_hour_column("0", date) == datetime(2026, 9, 4, 0, 0)

    def test_parse_hour_column_with_minutes(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Accept "H:MM" defensively — the sheet is not ours to control."""
        date = datetime(2026, 9, 4)
        assert parser._parse_hour_column("17:30", date) == datetime(2026, 9, 4, 17, 30)

    def test_parse_hour_column_preserves_date_and_zeroes_seconds(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Times hang off the event date with sub-minute precision cleared."""
        date = datetime(2026, 9, 4, 13, 45, 30, 123456)
        result = parser._parse_hour_column("17", date)
        assert result == datetime(2026, 9, 4, 17, 0, 0, 0)

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "12 AM",  # what the "GW Mobile" tab emits
            "Sat",  # mobile tab's end column
            "5PM",
            "noon",
            "24",  # out of range
            "17:99",  # invalid minutes
            "#VALUE!",
        ],
    )
    def test_parse_hour_column_unparseable(
        self, parser: ChucksGreenwoodParser, value: str
    ) -> None:
        """Anything that is not an hour yields None rather than a wrong time."""
        assert parser._parse_hour_column(value, datetime(2026, 9, 4)) is None

    def test_parse_hour_columns_pair(self, parser: ChucksGreenwoodParser) -> None:
        """Both columns are parsed independently."""
        date = datetime(2026, 9, 6)
        start, end = parser._parse_hour_columns("9", "12", date)
        assert start == datetime(2026, 9, 6, 9, 0)
        assert end == datetime(2026, 9, 6, 12, 0)

    def test_parse_hour_columns_partial(self, parser: ChucksGreenwoodParser) -> None:
        """A missing end hour does not discard a usable start hour."""
        date = datetime(2026, 9, 6)
        start, end = parser._parse_hour_columns("17", "", date)
        assert start == datetime(2026, 9, 6, 17, 0)
        assert end is None

    # FULL DATE COLUMN PARSING TESTS

    def test_parse_full_date_column(self, parser: ChucksGreenwoodParser) -> None:
        """Column A holds an explicit M/D/YYYY for the near-term rows."""
        assert parser._parse_full_date_column("9/4/2026") == datetime(2026, 9, 4)
        assert parser._parse_full_date_column("10/31/2026") == datetime(2026, 10, 31)

    @freeze_time("2026-09-05")
    def test_parse_full_date_column_needs_no_year_inference(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A January date reads as 2027 without the rollover heuristic."""
        assert parser._parse_full_date_column("1/15/2027") == datetime(2027, 1, 15)

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "Sun",  # the weekday form used past ~2 months out
            "Sep 4",
            "9/4/26",  # two-digit year
            "13/1/2026",  # month out of range
            "9/32/2026",  # day out of range
            "2/30/2026",  # not a real calendar date
        ],
    )
    def test_parse_full_date_column_rejects(
        self, parser: ChucksGreenwoodParser, value: str
    ) -> None:
        """Non-M/D/YYYY values fall through to the month+date column."""
        assert parser._parse_full_date_column(value) is None

    # CSV ROW PARSING TESTS

    @freeze_time("2026-09-05")
    def test_parse_csv_row_valid_food_truck(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Test parsing a valid food truck CSV row."""
        row = [
            "10/2/2026",
            "Oct 2",
            "17",
            "to",
            "21",
            "Food Truck",
            "Dinner: T'Juana",
            "8/21/2024",
            "8/21/2026",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is not None
        assert result.venue_key == "chucks-greenwood"
        assert result.venue_name == "Chuck's Hop Shop Greenwood"
        assert result.title == "T'Juana"
        assert result.date.year == 2026
        assert result.date.month == 10
        assert result.date.day == 2
        assert result.start_time == datetime(2026, 10, 2, 17, 0)
        assert result.end_time == datetime(2026, 10, 2, 21, 0)
        assert result.description is not None
        assert "Dinner: T'Juana" in result.description

    @freeze_time("2026-09-05")
    def test_parse_csv_row_weekday_column_a(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Rows past ~2 months out carry a weekday in column A, not a date."""
        row = [
            "Sun",
            "Nov 01",
            "9",
            "to",
            "14",
            "Food Truck",
            "Brunch: Sunny Up",
            "9/4/2017",
            "7/29/2026",
            "FALSE",
            "TRUE",
        ]

        result = parser._parse_csv_row(row)
        assert result is not None
        assert result.title == "Sunny Up"
        # Falls back to column B; the zero-padded day still parses
        assert result.date == datetime(2026, 11, 1)
        assert result.start_time == datetime(2026, 11, 1, 9, 0)
        assert result.end_time == datetime(2026, 11, 1, 14, 0)

    @freeze_time("2026-09-05")
    def test_parse_csv_row_mobile_tab_format_yields_no_times(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Regression: the "GW Mobile" tab's columns must not become midnight.

        That tab renders column C as "12 AM" and column E as a day of week.
        Reading it is what left this venue with no times; if it is ever
        configured again, the event should surface untimed rather than
        claiming a bogus midnight start.
        """
        row = [
            "Fri",
            "Oct 2",
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
        assert result.title == "T'Juana"
        assert result.start_time is None
        assert result.end_time is None

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

    def test_parse_csv_row_spreadsheet_error_name(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """A food truck row whose name is a spreadsheet error is skipped."""
        row = [
            "Fri",
            "Aug 1",
            "12 AM",
            "to",
            "Sat",
            "Food Truck",
            "#VALUE!",
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
            m.get(parser.venue.url, status=200, body=sample_html)

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
            m.get(parser.venue.url, status=200, body=mixed_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Should only have food truck events
                assert len(events) == 3
                event_names = [event.title for event in events]
                assert "T'Juana" in event_names
                assert "Good Morning Tacos" in event_names
                assert "Tat's Deli" in event_names

                # Should not have trivia or bingo events
                for event in events:
                    assert "Trivia" not in event.title
                    assert "Bingo" not in event.title

    @pytest.mark.asyncio
    @freeze_time("2025-08-05")
    async def test_parse_skips_spreadsheet_error_rows(
        self, parser: ChucksGreenwoodParser
    ) -> None:
        """Rows with #VALUE! source errors are skipped, real vendors kept.

        Mirrors the real Google Sheet, where near-term food-truck rows carry a
        #VALUE! formula error while later rows have real vendor names.
        """
        csv_with_errors = """Greenwood Events & Food Trucks,,,,,,,Date Created,Last Updated,All Day Event,Recurring Event
Fri,Aug 1,12 AM,to,Sat,Food Truck,#VALUE!,Fri,Fri,FALSE,TRUE
Sat,Aug 2,12 AM,to,Sat,Food Truck,#VALUE!,Sat,Fri,FALSE,TRUE
Sun,Aug 16,12 AM,to,Sat,Food Truck,Dinner: Georgia's Greek,Sat,Fri,FALSE,TRUE
Mon,Aug 17,12 AM,to,Sat,Food Truck,Dinner: Off the Rez,Sun,Wed,FALSE,TRUE"""

        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=csv_with_errors)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Only the two real vendors survive; #VALUE! rows are dropped.
                assert len(events) == 2
                event_names = [event.title for event in events]
                assert "Georgia's Greek" in event_names
                assert "Off the Rez" in event_names
                assert all("#VALUE!" not in name for name in event_names)

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
            m.get(parser.venue.url, status=200, body=rollover_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) == 2
                # All events should be in 2026 (next year from test date 2025-12-15)
                for event in events:
                    assert event.date.year == 2026
