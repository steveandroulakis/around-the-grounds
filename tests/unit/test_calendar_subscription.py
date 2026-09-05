"""Subscriber-facing behavior and branding across the deployment paths."""

from unittest.mock import patch

import pytest

from around_the_grounds.config.loader import load_site_config
from around_the_grounds.main import generate_web_data
from around_the_grounds.temporal.activities import ScrapeActivities, _site_from_dict
from tests.unit.test_ics_generator import make_web_data, make_web_event, parse, vevents


def test_ballard_attribution_keeps_title_clean():
    data = make_web_data(public_url="https://ballardfoodtrucks.com")
    event = vevents(data)[0]
    assert event["SUMMARY"] == "Woodshop BBQ @ Stoup Brewing"
    assert event["URL"] == "https://ballardfoodtrucks.com"
    assert "Curated by Ballard Food Trucks." in event["DESCRIPTION"]
    assert "https://ballardfoodtrucks.com" in event["DESCRIPTION"]
    assert "Times may change" in event["DESCRIPTION"]


def test_branding_is_generic_and_optional():
    event = vevents(make_web_data(public_url="https://example.org", site_name="Music"))[
        0
    ]
    assert "Curated by Music." in event["DESCRIPTION"]
    assert event["URL"] == "https://example.org"
    plain = vevents(make_web_data())[0]
    assert plain["URL"] == "https://stoupbrewing.com"
    assert "DESCRIPTION" not in plain


@pytest.mark.parametrize(
    "start,end,note",
    [
        (None, None, "Hours not published."),
        ("2026-08-13T17:00:00", None, "End time estimated"),
        ("2026-08-13T17:00:00", "bad", "End time estimated"),
    ],
)
def test_unknown_hours_are_explained(start, end, note):
    event = vevents(make_web_data([make_web_event(start_iso=start, end_iso=end)]))[0]
    assert note in event["DESCRIPTION"]


def test_subscription_does_not_block_availability_or_add_alarms():
    cal = parse(make_web_data())
    assert cal.walk("VEVENT")[0]["TRANSP"] == "TRANSPARENT"
    assert cal.walk("VALARM") == []


@pytest.mark.asyncio
async def test_public_url_survives_temporal_and_web_data():
    site = load_site_config("ballard-food-trucks")
    assert site.public_url == "https://ballardfoodtrucks.com"
    assert site.name == "Ballard Food Trucks"
    with patch(
        "around_the_grounds.temporal.activities.load_site_config", return_value=site
    ):
        payload = await ScrapeActivities().load_site(site.key)
    restored = _site_from_dict(payload)
    restored.generate_description = False
    data = await generate_web_data([], [], site=restored)
    assert data["public_url"] == site.public_url
    assert parse(data)["X-WR-CALNAME"] == "Ballard Food Trucks"
    payload.pop("public_url")
    assert _site_from_dict(payload).public_url == ""
    for key in ("park-slope-music", "childrens-events"):
        assert load_site_config(key).public_url == ""
