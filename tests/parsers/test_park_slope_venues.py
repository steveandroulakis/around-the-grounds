"""Tests that park-slope-music.json config loads and all venues resolve to parsers."""

import pytest

from around_the_grounds.config.loader import load_site_config
from around_the_grounds.parsers.registry import ParserRegistry


class TestParkSlopeMusicConfig:
    """Verify park-slope-music site config integrity."""

    def test_config_loads_all_venues(self) -> None:
        """park-slope-music.json loads with 6 venues."""
        config = load_site_config("park-slope-music")
        assert len(config.venues) == 6

    def test_all_venues_have_parsers(self) -> None:
        """Every venue in the config resolves to a parser class."""
        config = load_site_config("park-slope-music")
        for venue in config.venues:
            parser_cls = ParserRegistry.get_parser(venue)
            assert parser_cls is not None, (
                f"No parser for venue '{venue.key}' "
                f"(source_type: '{venue.source_type}')"
            )

    def test_venue_keys_unique(self) -> None:
        """All venue keys are unique within the config."""
        config = load_site_config("park-slope-music")
        keys = [v.key for v in config.venues]
        assert len(keys) == len(set(keys))

    def test_json_ld_venue_present(self) -> None:
        """Eastville Comedy uses json-ld source_type."""
        config = load_site_config("park-slope-music")
        eastville = [v for v in config.venues if v.key == "eastville-comedy"]
        assert len(eastville) == 1
        assert eastville[0].source_type == "json-ld"

    def test_tribe_wordpress_venue_present(self) -> None:
        """Industry City uses wordpress with response_path."""
        config = load_site_config("park-slope-music")
        ic = [v for v in config.venues if v.key == "industry-city"]
        assert len(ic) == 1
        assert ic[0].source_type == "wordpress"
        assert ic[0].parser_config.get("response_path") == "events"

    def test_html_venues_present(self) -> None:
        """Young Ethel's and Roulette use html source_type."""
        config = load_site_config("park-slope-music")
        html_venues = [
            v for v in config.venues
            if v.source_type == "html"
        ]
        html_keys = {v.key for v in html_venues}
        assert "young-ethels" in html_keys
        assert "roulette-bk" in html_keys
        assert "union-hall" in html_keys
