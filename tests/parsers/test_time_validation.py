"""Tests for event time validation and times_optional behaviour."""

import logging
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from around_the_grounds.models import Event, Venue
from around_the_grounds.scrapers.coordinator import ScraperCoordinator


def _make_venue(
    key: str = "test-venue",
    name: str = "Test Venue",
    times_optional: bool = False,
) -> Venue:
    config: dict = {
        "event_container": ".event",
        "title_selector": ".title",
        "date_selector": ".date",
    }
    if times_optional:
        config["times_optional"] = True
    return Venue(
        key=key,
        name=name,
        url="https://example.com/events",
        source_type="html",
        parser_config=config,
    )


def _make_event(
    venue: Venue,
    title: str = "Test Event",
    has_time: bool = True,
) -> Event:
    now = datetime.now()
    return Event(
        venue_key=venue.key,
        venue_name=venue.name,
        title=title,
        date=now,
        start_time=now if has_time else None,
        end_time=None,
        extraction_method="html",
    )


class TestTimeValidation:
    """Tests for time validation and times_optional flag."""

    def test_events_from_timed_venue_must_have_start_time(self) -> None:
        """Events from non-optional venues should have start_time set."""
        venue = _make_venue(times_optional=False)
        event_with_time = _make_event(venue, has_time=True)
        event_without_time = _make_event(venue, has_time=False)

        assert event_with_time.start_time is not None
        assert event_without_time.start_time is None
        # The event still exists — times are not enforced at the model level,
        # but the coordinator should warn about it.

    def test_events_from_times_optional_venue_may_lack_start_time(self) -> None:
        """Events from times_optional venues are allowed to lack start_time."""
        venue = _make_venue(times_optional=True)
        event = _make_event(venue, has_time=False)

        assert event.start_time is None
        assert venue.parser_config is not None
        assert venue.parser_config.get("times_optional") is True

    @pytest.mark.asyncio
    async def test_coordinator_warns_on_missing_times(self, caplog: pytest.LogCaptureFixture) -> None:
        """Coordinator logs a warning when non-optional venue events lack start_time."""
        venue = _make_venue(key="timed-venue", name="Timed Venue", times_optional=False)
        events = [
            _make_event(venue, title="Has Time", has_time=True),
            _make_event(venue, title="No Time", has_time=False),
        ]

        coordinator = ScraperCoordinator()

        mock_parser_class = MagicMock()
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse = AsyncMock(return_value=events)
        mock_parser_class.return_value = mock_parser_instance

        with patch(
            "around_the_grounds.scrapers.coordinator.ParserRegistry.get_parser",
            return_value=mock_parser_class,
        ):
            connector = MagicMock()
            session = AsyncMock()

            with caplog.at_level(logging.WARNING):
                result_events, error = await coordinator._scrape_venue(session, venue)

        assert error is None
        assert len(result_events) == 2
        assert any("missing start_time" in msg for msg in caplog.messages)

    @pytest.mark.asyncio
    async def test_coordinator_no_warning_for_times_optional(self, caplog: pytest.LogCaptureFixture) -> None:
        """No warning when times_optional venue events lack start_time."""
        venue = _make_venue(
            key="optional-venue", name="Optional Venue", times_optional=True
        )
        events = [
            _make_event(venue, title="No Time", has_time=False),
        ]

        coordinator = ScraperCoordinator()

        mock_parser_class = MagicMock()
        mock_parser_instance = MagicMock()
        mock_parser_instance.parse = AsyncMock(return_value=events)
        mock_parser_class.return_value = mock_parser_instance

        with patch(
            "around_the_grounds.scrapers.coordinator.ParserRegistry.get_parser",
            return_value=mock_parser_class,
        ):
            session = AsyncMock()

            with caplog.at_level(logging.WARNING):
                result_events, error = await coordinator._scrape_venue(session, venue)

        assert error is None
        assert len(result_events) == 1
        assert not any("missing start_time" in msg for msg in caplog.messages)
