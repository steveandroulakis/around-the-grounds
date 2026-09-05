"""Subscriber-facing behavior and branding across the deployment paths."""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from around_the_grounds.config.loader import load_site_config
from around_the_grounds.main import generate_web_data
from around_the_grounds.temporal.activities import ScrapeActivities, _site_from_dict
from tests.unit.test_ics_generator import make_web_data, make_web_event, parse, vevents


@pytest.mark.parametrize(
    "start,end,all_day",
    [
        ("2026-08-13T12:00:00", "2026-08-13T20:00:00", False),
        ("2026-08-13T11:59:00", "2026-08-13T20:00:00", True),
        ("2026-08-13T03:00:00", "2026-08-13T20:00:00", True),
        ("2026-08-13T22:00:00", "2026-08-13T02:00:00", False),
        (None, None, True),
        ("2026-08-13T17:00:00", None, False),
    ],
)
def test_duration_threshold(start, end, all_day):
    event = vevents(
        make_web_data(
            [make_web_event(start_iso=start, end_iso=end)],
            calendar_max_timed_hours=8,
        )
    )[0]
    assert (type(event["DTSTART"].dt) is date) == all_day
    if all_day:
        assert event["DTSTART"].dt == date(2026, 8, 13)
        assert event["DTEND"].dt == date(2026, 8, 14)


def test_uncertain_hours_preserve_context_and_identity(caplog):
    source = make_web_event(
        start_iso="2026-08-13T03:00:00", end_iso="2026-08-13T20:00:00"
    )
    data = make_web_data([source], calendar_max_timed_hours=8)
    event = vevents(data)[0]
    assert "Hours uncertain" in event["DESCRIPTION"]
    assert "03:00" in event["DESCRIPTION"] and "20:00" in event["DESCRIPTION"]
    assert "https://stoupbrewing.com" in event["DESCRIPTION"]
    assert "03:00" in caplog.text and "20:00" in caplog.text
    assert event["TRANSP"] == "TRANSPARENT"
    assert event["UID"] == vevents(make_web_data([source]))[0]["UID"]
    from around_the_grounds.utils.ics_generator import build_ics

    assert build_ics(data) == build_ics(data)


@pytest.mark.parametrize("limit", [None, 24])
def test_other_sites_or_configured_longer_shifts_remain_timed(limit):
    event = vevents(
        make_web_data(
            [
                make_web_event(
                    start_iso="2026-08-13T03:00:00", end_iso="2026-08-13T20:00:00"
                )
            ],
            calendar_max_timed_hours=limit,
        )
    )[0]
    assert isinstance(event["DTSTART"].dt, datetime)


@pytest.mark.parametrize("limit", [0, -1, "bad", float("inf"), float("nan")])
def test_invalid_threshold_does_not_break_feed(limit, caplog):
    event = vevents(make_web_data(calendar_max_timed_hours=limit))[0]
    assert isinstance(event["DTSTART"].dt, datetime)
    assert "Ignoring invalid calendar duration threshold" in caplog.text


def test_threshold_uses_elapsed_time_across_dst():
    # Nine wall-clock hours across spring-forward are eight elapsed hours.
    event = vevents(
        make_web_data(
            [
                make_web_event(
                    date="2026-03-08T00:00:00",
                    start_iso="2026-03-08T00:00:00-08:00",
                    end_iso="2026-03-08T09:00:00-07:00",
                )
            ],
            calendar_max_timed_hours=8,
        )
    )[0]
    assert isinstance(event["DTSTART"].dt, datetime)


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
    assert site.calendar_max_timed_hours == 8
    with patch(
        "around_the_grounds.temporal.activities.load_site_config", return_value=site
    ):
        payload = await ScrapeActivities().load_site(site.key)
    restored = _site_from_dict(payload)
    restored.generate_description = False
    data = await generate_web_data([], [], site=restored)
    assert data["public_url"] == site.public_url
    assert data["calendar_max_timed_hours"] == 8
    assert parse(data)["X-WR-CALNAME"] == "Ballard Food Trucks"
    payload.pop("public_url")
    payload.pop("calendar_max_timed_hours")
    assert _site_from_dict(payload).calendar_max_timed_hours is None
    assert _site_from_dict(payload).public_url == ""
    for key in ("park-slope-music", "childrens-events"):
        assert load_site_config(key).public_url == ""
        assert load_site_config(key).calendar_max_timed_hours is None
