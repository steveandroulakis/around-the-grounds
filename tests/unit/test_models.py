"""Unit tests for data models."""

import json
from datetime import datetime
from pathlib import Path

from around_the_grounds.config.loader import load_site_from_path
from around_the_grounds.models import Event, SiteConfig, Venue


class TestVenue:
    """Test the Venue model."""

    def test_venue_creation(self) -> None:
        """Test basic venue creation."""
        venue = Venue(
            key="test-key", name="Test Venue", url="https://example.com"
        )

        assert venue.key == "test-key"
        assert venue.name == "Test Venue"
        assert venue.url == "https://example.com"
        assert venue.source_type == "html"
        assert venue.parser_config == {}

    def test_venue_with_config(self) -> None:
        """Test venue creation with parser config."""
        config = {"test": "value"}
        venue = Venue(
            key="test-key",
            name="Test Venue",
            url="https://example.com",
            parser_config=config,
        )

        assert venue.parser_config == config

    def test_venue_source_type(self) -> None:
        """Test venue with custom source_type."""
        venue = Venue(
            key="wp-site",
            name="WP Site",
            url="https://example.com",
            source_type="wordpress",
        )
        assert venue.source_type == "wordpress"

    def test_venue_equality(self) -> None:
        """Test venue equality comparison."""
        venue1 = Venue("key1", "Name1", "url1")
        venue2 = Venue("key1", "Name1", "url1")
        venue3 = Venue("key2", "Name1", "url1")

        assert venue1 == venue2
        assert venue1 != venue3


class TestEvent:
    """Test the Event model."""

    def test_event_creation(self) -> None:
        """Test basic event creation."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event = Event(
            venue_key="test-venue",
            venue_name="Test Venue",
            title="Test Show",
            date=event_date,
        )

        assert event.venue_key == "test-venue"
        assert event.venue_name == "Test Venue"
        assert event.title == "Test Show"
        assert event.date == event_date
        assert event.start_time is None
        assert event.end_time is None
        assert event.description is None
        assert event.extraction_method == "html"

    def test_event_with_times(self) -> None:
        """Test event with start and end times."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)
        start_time = datetime(2025, 7, 5, 13, 0, 0)
        end_time = datetime(2025, 7, 5, 20, 0, 0)

        event = Event(
            venue_key="test-venue",
            venue_name="Test Venue",
            title="Test Show",
            date=event_date,
            start_time=start_time,
            end_time=end_time,
            description="Test description",
        )

        assert event.start_time == start_time
        assert event.end_time == end_time
        assert event.description == "Test description"

    def test_event_equality(self) -> None:
        """Test event equality comparison."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event1 = Event("key1", "Name1", "Show1", event_date)
        event2 = Event("key1", "Name1", "Show1", event_date)
        event3 = Event("key2", "Name1", "Show1", event_date)

        assert event1 == event2
        assert event1 != event3

    def test_event_string_representation(self) -> None:
        """Test string representation of event."""
        event_date = datetime(2025, 7, 5, 12, 0, 0)

        event = Event(
            venue_key="test-venue",
            venue_name="Test Venue",
            title="Test Show",
            date=event_date,
        )

        str_repr = str(event)
        assert "Test Show" in str_repr
        assert "Test Venue" in str_repr


class TestSiteConfig:
    """Test the SiteConfig model and loader."""

    def test_site_config_defaults(self) -> None:
        """deploy_subdir defaults to empty (root-deploy) for backward compat."""
        site = SiteConfig(
            key="test",
            name="Test Site",
            template="food-trucks",
            timezone="America/Los_Angeles",
            venues=[],
        )
        assert site.deploy_subdir == ""
        assert site.target_repo == ""
        assert site.generate_description is True

    def test_site_config_deploy_subdir(self) -> None:
        """deploy_subdir can be set explicitly for Vercel-style subfolder deploys."""
        site = SiteConfig(
            key="test",
            name="Test Site",
            template="food-trucks",
            timezone="America/Los_Angeles",
            venues=[],
            deploy_subdir="public",
        )
        assert site.deploy_subdir == "public"

    def test_loader_reads_deploy_subdir(self, tmp_path: Path) -> None:
        """Loader pulls deploy_subdir out of JSON when present."""
        config_path = tmp_path / "site.json"
        config_path.write_text(
            json.dumps(
                {
                    "key": "loader-test",
                    "name": "Loader Test",
                    "template": "food-trucks",
                    "timezone": "America/Los_Angeles",
                    "deploy_subdir": "public",
                    "venues": [],
                }
            )
        )
        site = load_site_from_path(config_path)
        assert site.deploy_subdir == "public"

    def test_loader_deploy_subdir_defaults_empty(self, tmp_path: Path) -> None:
        """Loader omits deploy_subdir when not in JSON — defaults to empty."""
        config_path = tmp_path / "site.json"
        config_path.write_text(
            json.dumps(
                {
                    "key": "loader-test",
                    "name": "Loader Test",
                    "template": "food-trucks",
                    "timezone": "America/Los_Angeles",
                    "venues": [],
                }
            )
        )
        site = load_site_from_path(config_path)
        assert site.deploy_subdir == ""
