"""Tests for Channel Marker Cider parser."""

from pathlib import Path

import aiohttp
import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from around_the_grounds.models import Venue
from around_the_grounds.parsers.channel_marker import ChannelMarkerParser


class TestChannelMarkerParser:
    """Test the ChannelMarkerParser class."""

    @pytest.fixture
    def venue(self) -> Venue:
        """Create a test venue for Channel Marker."""
        return Venue(
            key="channel-marker",
            name="Channel Marker Cider",
            url="https://docs.google.com/spreadsheets/d/e/2PACX-1vRaaJmiJ4YrKmvwiFdsHYij1kLUVP6394gMrTPpgHwu1zTtM5aoIy9JfLyeK4WrLLDDiHcFRAtbZci_/pub?output=csv",
            parser_config={
                "note": "Google Sheets CSV export with food truck schedule",
                "csv_direct": True,
            },
        )

    @pytest.fixture
    def parser(self, venue: Venue) -> ChannelMarkerParser:
        """Create a parser instance."""
        return ChannelMarkerParser(venue)

    @pytest.fixture
    def sample_csv(self, csv_fixtures_dir: Path) -> str:
        """Load sample CSV fixture."""
        fixture_path = csv_fixtures_dir / "channel_marker_sample.csv"
        return fixture_path.read_text()

    # SUCCESS CASES

    @pytest.mark.asyncio
    @freeze_time("2026-03-30")
    async def test_parse_sample_csv_data(
        self, parser: ChannelMarkerParser, sample_csv: str
    ) -> None:
        """Test parsing the sample CSV data."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                assert len(events) > 0
                assert all(event.venue_key == "channel-marker" for event in events)
                assert all(
                    event.venue_name == "Channel Marker Cider"
                    for event in events
                )
                assert all(event.title.strip() != "" for event in events)
                assert all(event.date is not None for event in events)

                event_names = [event.title for event in events]
                assert "Where Ya At, Matt?" in event_names
                assert "La Rivera Maya" in event_names
                assert "La Costenita" in event_names
                assert "Now Make Me A Sandwich" in event_names
                assert "Birrieria Pepe El Toro" in event_names
                assert "Kaosamai" in event_names
                assert "El Pachi Empanadas" in event_names

    @pytest.mark.asyncio
    @freeze_time("2026-03-30")
    async def test_skips_rows_without_food_truck(
        self, parser: ChannelMarkerParser, sample_csv: str
    ) -> None:
        """Test that rows without a food truck name are skipped."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Sample has 15 data rows but only 8 have food truck names
                assert len(events) == 8

    @pytest.mark.asyncio
    @freeze_time("2026-03-30")
    async def test_parse_times(
        self, parser: ChannelMarkerParser, sample_csv: str
    ) -> None:
        """Test that times are parsed correctly."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                # Find the LA COSTENITA event (5PM-9PM)
                costenita = [
                    e for e in events if e.title == "La Costenita"
                ][0]
                assert costenita.start_time is not None
                assert costenita.start_time.hour == 17
                assert costenita.end_time is not None
                assert costenita.end_time.hour == 21

                # Find a 5PM-8PM event
                maya = [
                    e for e in events if e.title == "La Rivera Maya"
                ][0]
                assert maya.start_time is not None
                assert maya.start_time.hour == 17
                assert maya.end_time is not None
                assert maya.end_time.hour == 20

    @pytest.mark.asyncio
    @freeze_time("2026-03-30")
    async def test_parse_dates(
        self, parser: ChannelMarkerParser, sample_csv: str
    ) -> None:
        """Test that dates are parsed correctly."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

                matt = [
                    e for e in events if e.title == "Where Ya At, Matt?"
                ][0]
                assert matt.date.year == 2026
                assert matt.date.month == 3
                assert matt.date.day == 31

    @pytest.mark.asyncio
    @freeze_time("2026-03-30")
    async def test_parse_with_redirect(
        self, parser: ChannelMarkerParser, sample_csv: str
    ) -> None:
        """Test parsing with Google CDN redirect."""
        redirect_url = "https://doc-0s-3s-sheets.googleusercontent.com/pub/example/csv"

        with aioresponses() as m:
            m.get(parser.venue.url, status=307, headers={"Location": redirect_url})
            m.get(redirect_url, status=200, body=sample_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) > 0

    # ERROR HANDLING TESTS

    @pytest.mark.asyncio
    async def test_parse_empty_csv(self, parser: ChannelMarkerParser) -> None:
        """Test parsing when CSV is empty."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body="")

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_header_only_csv(self, parser: ChannelMarkerParser) -> None:
        """Test parsing when CSV has only headers."""
        header_only_csv = "DATE,FOOD TRUCK,TIME,EVENT"

        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=header_only_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: ChannelMarkerParser) -> None:
        """Test handling of network errors."""
        with aioresponses() as m:
            m.get(parser.venue.url, exception=aiohttp.ClientError("Network error"))

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_error(self, parser: ChannelMarkerParser) -> None:
        """Test handling of HTTP errors."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=404)

            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError, match="Failed to parse CSV data"):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_malformed_csv(self, parser: ChannelMarkerParser) -> None:
        """Test handling of malformed CSV data."""
        malformed_csv = """Incomplete row,missing
Another,incomplete"""

        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=malformed_csv)

            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
                assert len(events) == 0

    # DATE PARSING TESTS

    def test_parse_date_m_d_yy(self, parser: ChannelMarkerParser) -> None:
        """Test date parsing with M/D/YY format."""
        result = parser._parse_date("3/31/26")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 31

    @freeze_time("2026-03-30")
    def test_parse_date_m_d_no_year(self, parser: ChannelMarkerParser) -> None:
        """Test date parsing with M/D format (no year)."""
        result = parser._parse_date("4/29")
        assert result is not None
        assert result.year == 2026
        assert result.month == 4
        assert result.day == 29

    def test_parse_date_invalid(self, parser: ChannelMarkerParser) -> None:
        """Test date parsing with invalid input."""
        assert parser._parse_date("") is None
        assert parser._parse_date("not-a-date") is None
        assert parser._parse_date("13/1/26") is None  # Invalid month
        assert parser._parse_date("1/32/26") is None  # Invalid day

    # TIME PARSING TESTS

    @freeze_time("2026-04-01")
    def test_parse_time_range_valid(self, parser: ChannelMarkerParser) -> None:
        """Test time range parsing."""
        from datetime import datetime

        event_date = datetime(2026, 4, 1)

        start, end = parser._parse_time_range("5PM-8PM", event_date)
        assert start is not None
        assert end is not None
        assert start.hour == 17
        assert end.hour == 20

        start, end = parser._parse_time_range("11AM-3PM", event_date)
        assert start is not None
        assert end is not None
        assert start.hour == 11
        assert end.hour == 15

    def test_parse_time_range_empty(self, parser: ChannelMarkerParser) -> None:
        """Test time range parsing with empty input."""
        from datetime import datetime

        event_date = datetime(2026, 4, 1)
        start, end = parser._parse_time_range("", event_date)
        assert start is None
        assert end is None

    def test_parse_time_range_invalid(self, parser: ChannelMarkerParser) -> None:
        """Test time range parsing with invalid input."""
        from datetime import datetime

        event_date = datetime(2026, 4, 1)
        start, end = parser._parse_time_range("sometime", event_date)
        assert start is None
        assert end is None

    # CSV ROW PARSING TESTS

    @freeze_time("2026-03-30")
    def test_parse_csv_row_valid(self, parser: ChannelMarkerParser) -> None:
        """Test parsing a valid CSV row."""
        row = ["3/31/26", "WHERE YA AT, MATT?", "5PM-8PM", "MUSIC BINGO (7-9PM)"]

        result = parser._parse_csv_row(row)
        assert result is not None
        assert result.venue_key == "channel-marker"
        assert result.venue_name == "Channel Marker Cider"
        assert result.title == "Where Ya At, Matt?"
        assert result.date.year == 2026
        assert result.date.month == 3
        assert result.date.day == 31
        assert result.start_time.hour == 17
        assert result.end_time.hour == 20

    def test_parse_csv_row_no_food_truck(self, parser: ChannelMarkerParser) -> None:
        """Test parsing a row with no food truck."""
        row = ["4/7/26", "", "", "MUSIC BINGO (7-9PM)"]

        result = parser._parse_csv_row(row)
        assert result is None

    def test_parse_csv_row_too_short(self, parser: ChannelMarkerParser) -> None:
        """Test parsing a CSV row that's too short."""
        row = ["3/31/26", "Some Truck"]

        result = parser._parse_csv_row(row)
        assert result is not None  # 2 columns is enough (date + truck name)

    def test_parse_csv_row_empty(self, parser: ChannelMarkerParser) -> None:
        """Test parsing an empty CSV row."""
        row = ["", "", "", ""]

        result = parser._parse_csv_row(row)
        assert result is None

    # 24-HOUR CONVERSION TESTS

    def test_to_24h(self, parser: ChannelMarkerParser) -> None:
        """Test 12-hour to 24-hour conversion."""
        assert parser._to_24h(12, "AM") == 0
        assert parser._to_24h(1, "AM") == 1
        assert parser._to_24h(11, "AM") == 11
        assert parser._to_24h(12, "PM") == 12
        assert parser._to_24h(1, "PM") == 13
        assert parser._to_24h(5, "PM") == 17
        assert parser._to_24h(0, "AM") is None  # Invalid
        assert parser._to_24h(13, "PM") is None  # Invalid
