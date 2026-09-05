"""Tests for the .ics calendar feed generator."""

from datetime import date, datetime, timedelta, timezone

import pytest
from icalendar import Calendar

from around_the_grounds.utils.ics_generator import (
    DEFAULT_EVENT_DURATION,
    build_ics,
)


def make_web_event(**overrides):
    """A timed web_event dict as produced by main.generate_web_data."""
    web_event = {
        "date": "2026-08-13T00:00:00",
        "title": "Woodshop BBQ",
        "venue": "Stoup Brewing",
        "venue_key": "stoup-ballard",
        "venue_url": "https://stoupbrewing.com",
        "start_iso": "2026-08-13T17:00:00",
        "end_iso": "2026-08-13T21:00:00",
        "start_time": "5:00 PM PT",
        "end_time": "9:00 PM PT",
        "description": None,
        "extraction_method": "html",
        "vendor": "Woodshop BBQ",
        "location": "Stoup Brewing",
    }
    web_event.update(overrides)
    return web_event


def make_web_data(events=None, **overrides):
    web_data = {
        "site_key": "ballard-food-trucks",
        "site_name": "Ballard Food Trucks",
        "timezone": "America/Los_Angeles",
        "total_events": len(events or []),
        "events": events if events is not None else [make_web_event()],
    }
    web_data.update(overrides)
    return web_data


def parse(web_data):
    """Build and re-parse, returning the Calendar object."""
    return Calendar.from_ical(build_ics(web_data))


def vevents(web_data):
    return parse(web_data).walk("VEVENT")


class TestCalendarProperties:
    def test_calendar_level_properties(self):
        cal = parse(make_web_data())

        assert cal["VERSION"] == "2.0"
        assert cal["PRODID"] == "-//Around the Grounds//ballard-food-trucks//EN"
        assert cal["CALSCALE"] == "GREGORIAN"
        assert cal["METHOD"] == "PUBLISH"
        assert cal["X-WR-CALNAME"] == "Ballard Food Trucks"
        assert cal["X-WR-TIMEZONE"] == "America/Los_Angeles"

    def test_refresh_interval_carries_value_parameter(self):
        # RFC 7986 REFRESH-INTERVAL must declare VALUE=DURATION.
        raw = build_ics(make_web_data())
        assert b"REFRESH-INTERVAL;VALUE=DURATION:PT6H" in raw
        assert b"X-PUBLISHED-TTL:PT6H" in raw

    def test_output_is_valid_parseable_ics(self):
        raw = build_ics(make_web_data())
        assert raw.startswith(b"BEGIN:VCALENDAR")
        assert raw.rstrip().endswith(b"END:VCALENDAR")
        assert len(Calendar.from_ical(raw).walk("VEVENT")) == 1

    def test_empty_event_list_still_produces_a_valid_calendar(self):
        cal = parse(make_web_data(events=[]))
        assert cal.walk("VEVENT") == []

    def test_missing_optional_keys_fall_back_to_defaults(self):
        cal = Calendar.from_ical(build_ics({"events": []}))
        assert cal["PRODID"] == "-//Around the Grounds//events//EN"
        assert cal["X-WR-CALNAME"] == "Events"


class TestTimedEvents:
    def test_times_are_converted_from_site_local_to_utc(self):
        ve = vevents(make_web_data())[0]

        # 5:00 PM PDT (UTC-7) on Aug 13 == 00:00 UTC on Aug 14.
        assert ve["DTSTART"].dt == datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)
        assert ve["DTEND"].dt == datetime(2026, 8, 14, 4, 0, tzinfo=timezone.utc)

    def test_utc_offset_respects_dst(self):
        """A January event uses PST (UTC-8), not PDT (UTC-7)."""
        winter = make_web_event(
            date="2026-01-15T00:00:00",
            start_iso="2026-01-15T17:00:00",
            end_iso="2026-01-15T21:00:00",
        )
        ve = vevents(make_web_data([winter]))[0]

        assert ve["DTSTART"].dt == datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc)

    def test_site_timezone_is_honoured(self):
        eastern = make_web_data(
            [make_web_event()], timezone="America/New_York", site_key="park-slope-music"
        )
        ve = vevents(eastern)[0]

        # 5:00 PM EDT (UTC-4) == 21:00 UTC.
        assert ve["DTSTART"].dt == datetime(2026, 8, 13, 21, 0, tzinfo=timezone.utc)

    def test_missing_end_time_gets_default_duration(self):
        ve = vevents(make_web_data([make_web_event(end_iso=None)]))[0]

        assert ve["DTEND"].dt - ve["DTSTART"].dt == DEFAULT_EVENT_DURATION

    def test_end_before_start_rolls_over_to_next_day(self):
        """A listing that closes past midnight must not produce a negative span."""
        late = make_web_event(
            start_iso="2026-08-13T21:00:00", end_iso="2026-08-13T01:00:00"
        )
        ve = vevents(make_web_data([late]))[0]

        assert ve["DTEND"].dt > ve["DTSTART"].dt
        assert ve["DTEND"].dt - ve["DTSTART"].dt == timedelta(hours=4)

    def test_timezone_aware_iso_input_is_respected(self):
        """Some parsers emit aware datetimes; the offset must not be re-applied."""
        aware = make_web_event(
            start_iso="2026-08-13T17:00:00+00:00", end_iso="2026-08-13T21:00:00+00:00"
        )
        ve = vevents(make_web_data([aware]))[0]

        assert ve["DTSTART"].dt == datetime(2026, 8, 13, 17, 0, tzinfo=timezone.utc)


class TestAllDayEvents:
    def test_no_start_time_produces_an_all_day_event(self):
        ve = vevents(make_web_data([make_web_event(start_iso=None, end_iso=None)]))[0]

        assert ve["DTSTART"].dt == date(2026, 8, 13)
        assert ve["DTEND"].dt == date(2026, 8, 14)
        assert not isinstance(ve["DTSTART"].dt, datetime)

    def test_all_day_events_use_the_date_value_type(self):
        raw = build_ics(make_web_data([make_web_event(start_iso=None, end_iso=None)]))
        assert b"DTSTART;VALUE=DATE:20260813" in raw
        assert b"DTEND;VALUE=DATE:20260814" in raw


class TestFieldMapping:
    def test_summary_combines_title_and_venue(self):
        ve = vevents(make_web_data())[0]
        assert ve["SUMMARY"] == "Woodshop BBQ @ Stoup Brewing"

    def test_summary_uses_plain_title_not_the_vendor_emoji_variant(self):
        """The 'vendor' key carries a 🖼️🤖 suffix that is a web-only affordance."""
        ai = make_web_event(
            title="Mystery Truck",
            vendor="Mystery Truck 🖼️🤖",
            extraction_method="vision",
        )
        ve = vevents(make_web_data([ai]))[0]

        assert ve["SUMMARY"] == "Mystery Truck @ Stoup Brewing"
        assert "🖼️" not in str(ve["SUMMARY"])

    def test_summary_omits_separator_when_venue_is_unknown(self):
        ve = vevents(make_web_data([make_web_event(venue=None, location=None)]))[0]
        assert ve["SUMMARY"] == "Woodshop BBQ"

    def test_location_and_url(self):
        ve = vevents(make_web_data())[0]

        assert ve["LOCATION"] == "Stoup Brewing"
        assert ve["URL"] == "https://stoupbrewing.com"

    def test_url_omitted_when_venue_url_unknown(self):
        ve = vevents(make_web_data([make_web_event(venue_url=None)]))[0]
        assert "URL" not in ve

    def test_description_passed_through(self):
        ve = vevents(make_web_data([make_web_event(description="Smoked meats")]))[0]
        assert ve["DESCRIPTION"] == "Smoked meats"

    def test_description_omitted_when_empty(self):
        ve = vevents(make_web_data())[0]
        assert "DESCRIPTION" not in ve

    def test_vision_events_are_annotated(self):
        ai = make_web_event(extraction_method="vision", description="Tacos")
        ve = vevents(make_web_data([ai]))[0]

        assert "Tacos" in str(ve["DESCRIPTION"])
        assert "AI image analysis" in str(ve["DESCRIPTION"])

    def test_vision_annotation_alone_when_no_description(self):
        ai = make_web_event(extraction_method="vision", description=None)
        ve = vevents(make_web_data([ai]))[0]

        assert str(ve["DESCRIPTION"]) == "Vendor name extracted by AI image analysis."

    def test_special_characters_are_escaped(self):
        tricky = make_web_event(title='Tacos, Inc; "Best" \\ Trucks')
        raw = build_ics(make_web_data([tricky]))

        # RFC 5545 requires commas and semicolons in TEXT values to be escaped.
        assert b"Tacos\\, Inc\\; " in raw
        # And it must survive a round trip intact.
        ve = Calendar.from_ical(raw).walk("VEVENT")[0]
        assert str(ve["SUMMARY"]) == 'Tacos, Inc; "Best" \\ Trucks @ Stoup Brewing'

    def test_events_preserve_input_order(self):
        events = [
            make_web_event(title="First"),
            make_web_event(title="Second", date="2026-08-14T00:00:00"),
            make_web_event(title="Third", date="2026-08-15T00:00:00"),
        ]
        summaries = [str(ve["SUMMARY"]) for ve in vevents(make_web_data(events))]

        assert [s.split(" @ ")[0] for s in summaries] == ["First", "Second", "Third"]


class TestUids:
    def test_uid_is_stable_across_calls(self):
        web_data = make_web_data()
        first = vevents(web_data)[0]["UID"]
        second = vevents(web_data)[0]["UID"]

        assert str(first) == str(second)
        assert str(first).endswith("@around-the-grounds")

    def test_uid_differs_by_venue(self):
        a = make_web_event(venue_key="stoup-ballard")
        b = make_web_event(venue_key="obec-brewing")
        uids = [str(ve["UID"]) for ve in vevents(make_web_data([a, b]))]

        assert uids[0] != uids[1]

    def test_uid_differs_by_date_and_title(self):
        base = make_web_event()
        other_date = make_web_event(date="2026-08-14T00:00:00")
        other_title = make_web_event(title="Different Truck")
        uids = [
            str(ve["UID"])
            for ve in vevents(make_web_data([base, other_date, other_title]))
        ]

        assert len(set(uids)) == 3

    def test_uid_survives_a_changed_start_time(self):
        """Rescheduling a truck updates the existing entry rather than duplicating."""
        original = make_web_data([make_web_event(start_iso="2026-08-13T17:00:00")])
        moved = make_web_data([make_web_event(start_iso="2026-08-13T18:00:00")])

        assert str(vevents(original)[0]["UID"]) == str(vevents(moved)[0]["UID"])


class TestDeterminism:
    def test_identical_input_produces_identical_bytes(self):
        """Guards the no-op deploy short-circuit in _deploy_with_github_auth.

        If DTSTAMP were datetime.now(), every scheduled scrape would produce a
        diff and therefore an empty commit.
        """
        web_data = make_web_data(
            [
                make_web_event(),
                make_web_event(start_iso=None, end_iso=None, title="All Day"),
            ]
        )

        assert build_ics(web_data) == build_ics(web_data)

    def test_dtstamp_is_derived_from_the_event_not_now(self):
        ve = vevents(make_web_data())[0]
        assert ve["DTSTAMP"].dt == ve["DTSTART"].dt

    def test_all_day_dtstamp_is_a_utc_datetime(self):
        # RFC 5545 requires DTSTAMP to be a UTC DATE-TIME even for all-day events.
        ve = vevents(make_web_data([make_web_event(start_iso=None, end_iso=None)]))[0]

        assert isinstance(ve["DTSTAMP"].dt, datetime)
        assert ve["DTSTAMP"].dt == datetime(2026, 8, 13, tzinfo=timezone.utc)


class TestMalformedInput:
    def test_event_without_a_date_is_skipped(self):
        good = make_web_event()
        bad = make_web_event(date=None, title="Undated")

        assert len(vevents(make_web_data([good, bad]))) == 1

    def test_unparseable_start_time_falls_back_to_all_day(self):
        ve = vevents(make_web_data([make_web_event(start_iso="not-a-date")]))[0]
        assert ve["DTSTART"].dt == date(2026, 8, 13)

    def test_unknown_timezone_falls_back_to_default(self):
        web_data = make_web_data(timezone="Mars/Olympus_Mons")
        ve = vevents(web_data)[0]

        # Falls back to America/Los_Angeles: 5 PM PDT == 00:00 UTC next day.
        assert ve["DTSTART"].dt == datetime(2026, 8, 14, 0, 0, tzinfo=timezone.utc)

    def test_missing_title_gets_a_placeholder(self):
        ve = vevents(make_web_data([make_web_event(title=None)]))[0]
        assert str(ve["SUMMARY"]) == "Event @ Stoup Brewing"
