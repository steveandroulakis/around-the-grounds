"""SiteConfig <-> dict round-trip shared by the loader and the Temporal boundary."""

import json
from pathlib import Path

import pytest

from around_the_grounds.config.loader import (
    load_all_sites,
    site_from_dict,
    site_to_dict,
)
from around_the_grounds.models import SiteConfig, Venue

SITES_DIR = (
    Path(__file__).resolve().parents[2] / "around_the_grounds" / "config" / "sites"
)


@pytest.mark.parametrize(
    "config_path", sorted(SITES_DIR.glob("*.json")), ids=lambda p: p.stem
)
def test_checked_in_site_configs_survive_round_trip(config_path: Path) -> None:
    """Every real site config reloads identically after passing through a dict."""
    with open(config_path) as f:
        raw = json.load(f)
    site = site_from_dict(raw)
    payload = site_to_dict(site)

    # The payload is JSON-serializable (it crosses the activity boundary as JSON).
    json.dumps(payload)

    assert site_from_dict(payload) == site
    assert payload["venues"][0]["parser_config"] == site.venues[0].parser_config


def test_site_to_dict_contains_every_field() -> None:
    site = SiteConfig(
        key="k",
        name="N",
        template="music",
        timezone="America/New_York",
        venues=[
            Venue(
                key="v",
                name="V",
                url="https://v",
                source_type="ajax",
                parser_config={"a": 1},
            )
        ],
        target_repo="https://github.com/x/y.git",
        generate_description=False,
        deploy_subdir="public",
        public_url="https://example.com",
        calendar_max_timed_hours=6.5,
    )
    assert site_to_dict(site) == {
        "key": "k",
        "name": "N",
        "template": "music",
        "timezone": "America/New_York",
        "venues": [
            {
                "key": "v",
                "name": "V",
                "url": "https://v",
                "source_type": "ajax",
                "parser_config": {"a": 1},
            }
        ],
        "target_repo": "https://github.com/x/y.git",
        "generate_description": False,
        "deploy_subdir": "public",
        "public_url": "https://example.com",
        "calendar_max_timed_hours": 6.5,
    }


def test_site_from_dict_applies_defaults_for_legacy_payloads() -> None:
    """A payload persisted before newer fields existed still loads."""
    site = site_from_dict(
        {"key": "k", "name": "N", "venues": [{"key": "v", "name": "V", "url": "u"}]}
    )
    assert site.template == "food-trucks"
    assert site.timezone == "America/Los_Angeles"
    assert site.deploy_subdir == ""
    assert site.public_url == ""
    assert site.calendar_max_timed_hours is None
    assert site.venues[0].source_type == "html"
    assert site.venues[0].parser_config == {}


def test_load_all_sites_uses_shared_parser() -> None:
    sites = load_all_sites()
    assert {s.key for s in sites} >= {
        "ballard-food-trucks",
        "park-slope-music",
        "childrens-events",
    }
    ballard = next(s for s in sites if s.key == "ballard-food-trucks")
    assert ballard.deploy_subdir == "public"
