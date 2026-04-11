"""Tests for Lucky Envelope Brewing parser."""

import os
from datetime import datetime
from unittest.mock import Mock

import aiohttp
import pytest
from aioresponses import aioresponses

from around_the_grounds.models import Venue
from around_the_grounds.parsers.lucky_envelope import LuckyEnvelopeParser


class TestLuckyEnvelopeParser:
    """Test the LuckyEnvelopeParser class."""

    @pytest.fixture
    def venue(self) -> Venue:
        return Venue(
            key="lucky-envelope",
            name="Lucky Envelope Brewing",
            url="https://www.luckyenvelopebrewing.com/",
            parser_config={
                "note": "Squarespace page with embedded JSON in data-current-context carousel attribute"
            },
        )

    @pytest.fixture
    def parser(self, venue: Venue) -> LuckyEnvelopeParser:
        return LuckyEnvelopeParser(venue)

    @pytest.fixture
    def sample_html(self) -> str:
        fixture_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "fixtures",
            "html",
            "lucky_envelope_sample.html",
        )
        with open(fixture_path, "r") as f:
            return f.read()

    # --- Happy path ---

    @pytest.mark.asyncio
    async def test_parse_returns_events_from_fixture(
        self, parser: LuckyEnvelopeParser, sample_html: str
    ) -> None:
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_html)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        assert len(events) == 4
        names = [e.title for e in events]
        assert "El Koreano" in names
        assert "Tacos El Cunado" in names
        assert "Noodle Haus" in names
        assert "Burger Beast" in names

    @pytest.mark.asyncio
    async def test_parse_event_fields(
        self, parser: LuckyEnvelopeParser, sample_html: str
    ) -> None:
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_html)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        el_koreano = next(e for e in events if e.title == "El Koreano")
        assert el_koreano.venue_key == "lucky-envelope"
        assert el_koreano.venue_name == "Lucky Envelope Brewing"
        assert el_koreano.date == datetime(2026, 3, 13)
        assert el_koreano.start_time is not None
        assert el_koreano.start_time.hour == 17  # 5pm
        assert el_koreano.end_time is not None
        assert el_koreano.end_time.hour == 20  # 8pm

    @pytest.mark.asyncio
    async def test_parse_time_without_start_ampm(
        self, parser: LuckyEnvelopeParser, sample_html: str
    ) -> None:
        """4:30-7:30pm: start should inherit pm from end."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_html)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        tacos = next(e for e in events if e.title == "Tacos El Cunado")
        assert tacos.start_time is not None
        assert tacos.start_time.hour == 16  # 4:30pm
        assert tacos.start_time.minute == 30
        assert tacos.end_time is not None
        assert tacos.end_time.hour == 19  # 7:30pm
        assert tacos.end_time.minute == 30

    @pytest.mark.asyncio
    async def test_parse_time_both_ampm(
        self, parser: LuckyEnvelopeParser, sample_html: str
    ) -> None:
        """4:30pm-8pm: both have am/pm explicitly."""
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=sample_html)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)

        noodle = next(e for e in events if e.title == "Noodle Haus")
        assert noodle.start_time is not None
        assert noodle.start_time.hour == 16  # 4:30pm
        assert noodle.start_time.minute == 30
        assert noodle.end_time is not None
        assert noodle.end_time.hour == 20  # 8pm

    # --- Empty / missing cases ---

    @pytest.mark.asyncio
    async def test_parse_no_carousel_element(self, parser: LuckyEnvelopeParser) -> None:
        html_content = "<html><body><p>No carousel here</p></body></html>"
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=html_content)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        assert events == []

    @pytest.mark.asyncio
    async def test_parse_empty_user_items(self, parser: LuckyEnvelopeParser) -> None:
        html_content = """
        <html><body>
        <div class="user-items-list-carousel" data-current-context="{&quot;userItems&quot;:[]}">
        </div></body></html>
        """
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=html_content)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        assert events == []

    @pytest.mark.asyncio
    async def test_parse_missing_data_current_context(
        self, parser: LuckyEnvelopeParser
    ) -> None:
        html_content = """
        <html><body>
        <div class="user-items-list-carousel"></div>
        </body></html>
        """
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=html_content)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        assert events == []

    @pytest.mark.asyncio
    async def test_parse_invalid_json_in_attribute(
        self, parser: LuckyEnvelopeParser
    ) -> None:
        html_content = """
        <html><body>
        <div class="user-items-list-carousel" data-current-context="not-valid-json">
        </div></body></html>
        """
        with aioresponses() as m:
            m.get(parser.venue.url, status=200, body=html_content)
            async with aiohttp.ClientSession() as session:
                events = await parser.parse(session)
        assert events == []

    # --- Network / HTTP errors ---

    @pytest.mark.asyncio
    async def test_parse_network_error(self, parser: LuckyEnvelopeParser) -> None:
        with aioresponses() as m:
            m.get(parser.venue.url, exception=aiohttp.ClientError("Network error"))
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_404(self, parser: LuckyEnvelopeParser) -> None:
        with aioresponses() as m:
            m.get(parser.venue.url, status=404)
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError):
                    await parser.parse(session)

    @pytest.mark.asyncio
    async def test_parse_http_500(self, parser: LuckyEnvelopeParser) -> None:
        with aioresponses() as m:
            m.get(parser.venue.url, status=500)
            async with aiohttp.ClientSession() as session:
                with pytest.raises(ValueError):
                    await parser.parse(session)

    # --- Unit tests for _parse_date ---

    def test_parse_date_standard_format(self, parser: LuckyEnvelopeParser) -> None:
        result = parser._parse_date("Fri 3/13/26")
        assert result == datetime(2026, 3, 13)

    def test_parse_date_two_digit_year(self, parser: LuckyEnvelopeParser) -> None:
        result = parser._parse_date("Mon 1/5/25")
        assert result == datetime(2025, 1, 5)

    def test_parse_date_four_digit_year(self, parser: LuckyEnvelopeParser) -> None:
        result = parser._parse_date("Sat 12/25/2026")
        assert result == datetime(2026, 12, 25)

    def test_parse_date_no_date(self, parser: LuckyEnvelopeParser) -> None:
        result = parser._parse_date("No date here")
        assert result is None

    def test_parse_date_empty(self, parser: LuckyEnvelopeParser) -> None:
        result = parser._parse_date("")
        assert result is None

    # --- Unit tests for _parse_time_range ---

    def test_parse_time_range_simple(self, parser: LuckyEnvelopeParser) -> None:
        """5pm-8pm"""
        date = datetime(2026, 3, 13)
        start, end = parser._parse_time_range("5pm-8pm", date)
        assert start is not None and start.hour == 17
        assert end is not None and end.hour == 20

    def test_parse_time_range_inherit_ampm(self, parser: LuckyEnvelopeParser) -> None:
        """4:30-7:30pm: start inherits pm from end"""
        date = datetime(2026, 3, 14)
        start, end = parser._parse_time_range("4:30-7:30pm", date)
        assert start is not None
        assert start.hour == 16
        assert start.minute == 30
        assert end is not None
        assert end.hour == 19
        assert end.minute == 30

    def test_parse_time_range_both_explicit_ampm(
        self, parser: LuckyEnvelopeParser
    ) -> None:
        """4:30pm-8pm"""
        date = datetime(2026, 3, 15)
        start, end = parser._parse_time_range("4:30pm-8pm", date)
        assert start is not None
        assert start.hour == 16
        assert start.minute == 30
        assert end is not None
        assert end.hour == 20

    def test_parse_time_range_noon(self, parser: LuckyEnvelopeParser) -> None:
        """12pm-3pm"""
        date = datetime(2026, 3, 16)
        start, end = parser._parse_time_range("12pm-3pm", date)
        assert start is not None and start.hour == 12
        assert end is not None and end.hour == 15

    def test_parse_time_range_no_match(self, parser: LuckyEnvelopeParser) -> None:
        date = datetime(2026, 3, 13)
        start, end = parser._parse_time_range("no time here", date)
        assert start is None
        assert end is None

    def test_parse_time_range_empty(self, parser: LuckyEnvelopeParser) -> None:
        date = datetime(2026, 3, 13)
        start, end = parser._parse_time_range("", date)
        assert start is None
        assert end is None

    def test_parse_time_range_date_preserved(self, parser: LuckyEnvelopeParser) -> None:
        """Returned datetimes should carry the event_date's date component."""
        date = datetime(2026, 3, 13)
        start, end = parser._parse_time_range("5pm-8pm", date)
        assert start is not None
        assert start.year == 2026
        assert start.month == 3
        assert start.day == 13
