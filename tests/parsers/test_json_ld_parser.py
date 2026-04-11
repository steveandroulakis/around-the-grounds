"""Tests for the generic JSON-LD parser."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from around_the_grounds.models import Venue, Event
from around_the_grounds.parsers.generic.json_ld import JsonLdParser


def _make_venue(
    key: str = "eastville-comedy",
    url: str = "https://www.eastvillecomedy.com/calendar",
    parser_config: dict = None,
) -> Venue:
    """Helper to create a test Venue for JSON-LD parsing."""
    return Venue(
        key=key,
        name="Eastville Comedy Club",
        url=url,
        source_type="json-ld",
        parser_config=parser_config or {},
    )


def _make_html(json_ld: str, extra_ld: str = "") -> str:
    """Wrap JSON-LD string in minimal HTML."""
    parts = [
        '<html><head>',
        f'<script type="application/ld+json">{json_ld}</script>',
    ]
    if extra_ld:
        parts.append(
            f'<script type="application/ld+json">{extra_ld}</script>'
        )
    parts.append("</head><body></body></html>")
    return "".join(parts)


EDT = timezone(timedelta(hours=-4))


class TestJsonLdParser:
    """Tests for JsonLdParser."""

    @pytest.mark.asyncio
    async def test_parse_returns_events(self) -> None:
        """Parser extracts events from JSON-LD array."""
        html = _make_html(
            '[{"@type":"ComedyEvent","name":"Show A",'
            '"startDate":"2025-07-04T20:00:00-04:00"}]'
        )
        venue = _make_venue()
        parser = JsonLdParser(venue)

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 1
        assert events[0].title == "Show A"
        assert events[0].venue_key == "eastville-comedy"
        assert events[0].extraction_method == "json-ld"

    @pytest.mark.asyncio
    async def test_parse_extracts_start_and_end_times(self) -> None:
        """ISO dates are parsed into date, start_time, and end_time."""
        html = _make_html(
            '[{"@type":"Event","name":"Jazz",'
            '"startDate":"2025-07-04T20:00:00-04:00",'
            '"endDate":"2025-07-04T22:00:00-04:00"}]'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events[0].date == datetime(2025, 7, 4, 20, 0, tzinfo=EDT)
        assert events[0].start_time == datetime(2025, 7, 4, 20, 0, tzinfo=EDT)
        assert events[0].end_time == datetime(2025, 7, 4, 22, 0, tzinfo=EDT)

    @pytest.mark.asyncio
    async def test_parse_extracts_description(self) -> None:
        """Description field is mapped."""
        html = _make_html(
            '[{"@type":"Event","name":"Show",'
            '"startDate":"2025-07-04T20:00:00-04:00",'
            '"description":"A great show."}]'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events[0].description == "A great show."

    @pytest.mark.asyncio
    async def test_parse_no_jsonld_scripts(self) -> None:
        """Page without JSON-LD returns empty list."""
        html = "<html><head></head><body></body></html>"
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_skips_non_event_types(self) -> None:
        """Non-event JSON-LD types (Organization, etc.) are ignored."""
        html = _make_html(
            '{"@type":"Organization","name":"Acme Corp","url":"https://acme.com"}',
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_handles_graph_wrapper(self) -> None:
        """Events inside @graph wrapper are extracted."""
        html = _make_html(
            '{"@graph":[{"@type":"MusicEvent","name":"Band Night",'
            '"startDate":"2025-07-04T21:00:00-04:00"}]}'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 1
        assert events[0].title == "Band Night"

    @pytest.mark.asyncio
    async def test_parse_handles_type_as_list(self) -> None:
        """@type as a list is recognized."""
        html = _make_html(
            '[{"@type":["Event","SocialEvent"],"name":"Mixer",'
            '"startDate":"2025-07-04T18:00:00-04:00"}]'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 1
        assert events[0].title == "Mixer"

    @pytest.mark.asyncio
    async def test_parse_skips_event_missing_name(self) -> None:
        """Event without name is skipped."""
        html = _make_html(
            '[{"@type":"Event","startDate":"2025-07-04T20:00:00-04:00"}]'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_skips_event_missing_start_date(self) -> None:
        """Event without startDate is skipped."""
        html = _make_html('[{"@type":"Event","name":"No Date"}]')
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_skips_invalid_date(self) -> None:
        """Unparseable ISO date causes event to be skipped."""
        html = _make_html(
            '[{"@type":"Event","name":"Bad Date",'
            '"startDate":"not-a-date"}]'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert events == []

    @pytest.mark.asyncio
    async def test_parse_invalid_json_skipped(self) -> None:
        """Malformed JSON in script tag is skipped gracefully."""
        html = (
            '<html><head>'
            '<script type="application/ld+json">{bad json!</script>'
            '<script type="application/ld+json">'
            '[{"@type":"Event","name":"Good","startDate":"2025-07-04T20:00:00-04:00"}]'
            '</script>'
            '</head><body></body></html>'
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 1
        assert events[0].title == "Good"

    @pytest.mark.asyncio
    async def test_parse_custom_event_types(self) -> None:
        """parser_config.event_types filters to specified types only."""
        html = _make_html(
            '[{"@type":"ComedyEvent","name":"Comedy",'
            '"startDate":"2025-07-04T20:00:00-04:00"},'
            '{"@type":"MusicEvent","name":"Music",'
            '"startDate":"2025-07-05T20:00:00-04:00"}]'
        )
        venue = _make_venue(
            parser_config={"event_types": ["ComedyEvent"]}
        )
        parser = JsonLdParser(venue)

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 1
        assert events[0].title == "Comedy"

    @pytest.mark.asyncio
    async def test_parse_multiple_ld_blocks(self) -> None:
        """Events from multiple JSON-LD blocks are combined."""
        html = _make_html(
            '[{"@type":"Event","name":"Event A",'
            '"startDate":"2025-07-04T20:00:00-04:00"}]',
            extra_ld=(
                '[{"@type":"Event","name":"Event B",'
                '"startDate":"2025-07-05T20:00:00-04:00"}]'
            ),
        )
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        assert len(events) == 2
        titles = {e.title for e in events}
        assert titles == {"Event A", "Event B"}

    @pytest.mark.asyncio
    async def test_parse_with_fixture_file(self) -> None:
        """Parser correctly handles the Eastville Comedy fixture."""
        fixture_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "html"
            / "eastville_comedy_sample.html"
        )
        html = fixture_path.read_text()
        parser = JsonLdParser(_make_venue())

        with patch.object(
            parser, "fetch_page", return_value=BeautifulSoup(html, "lxml")
        ):
            events = await parser.parse(MagicMock())

        # Fixture has 2 ComedyEvents + 1 Organization (skipped)
        assert len(events) == 2
        assert events[0].title == "Friday Night Standup"
        assert events[1].title == "Saturday Late Show"
        assert events[0].end_time is not None
        assert events[1].end_time is None
