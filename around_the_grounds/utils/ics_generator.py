"""Render generated web data as an RFC 5545 iCalendar (.ics) feed.

The feed is published alongside ``data.json`` so that anyone can subscribe to
the schedule in Google Calendar, Apple Calendar, or Outlook instead of having
to visit the website.

The input is the ``web_data`` dict produced by
:func:`around_the_grounds.main.generate_web_data`.  Consuming that dict rather
than ``List[Event]`` is deliberate: the Temporal ``deploy_to_git`` activity
only ever receives ``web_data``, so deriving the calendar from it keeps the
CLI and Temporal deploy paths on one implementation.
"""

import hashlib
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from icalendar import Calendar
from icalendar import Event as CalendarEvent

try:
    from zoneinfo import ZoneInfo  # type: ignore
except ImportError:
    from backports.zoneinfo import ZoneInfo  # type: ignore

logger = logging.getLogger(__name__)

# Events whose venue publishes a start but no end time get this duration so
# they render as a readable block instead of a zero-length instant (RFC 5545
# treats a VEVENT with neither DTEND nor DURATION as zero-length).
DEFAULT_EVENT_DURATION = timedelta(hours=3)

DEFAULT_TIMEZONE = "America/Los_Angeles"
UID_DOMAIN = "around-the-grounds"

# Ask subscribing clients to re-poll a few times a day. Both spellings are
# needed in practice: REFRESH-INTERVAL is the RFC 7986 property, X-PUBLISHED-TTL
# is the older Outlook/Google convention.
REFRESH_INTERVAL = "PT6H"


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string, returning None if absent or unparseable."""
    if not value:
        return None
    try:
        # Python 3.9's fromisoformat does not accept a trailing "Z".
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        logger.warning("Skipping unparseable datetime in calendar feed: %r", value)
        return None


def _to_utc(dt: datetime, tz: ZoneInfo) -> datetime:
    """Convert a datetime to UTC, assuming site-local time when naive.

    Emitting UTC keeps every DTSTART/DTEND a simple ``...Z`` value, which
    avoids shipping a VTIMEZONE block and is handled correctly by every
    calendar client.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


def _resolve_timezone(tz_name: Optional[str]) -> ZoneInfo:
    """Return the site's ZoneInfo, falling back to the default on a bad name."""
    try:
        return ZoneInfo(tz_name or DEFAULT_TIMEZONE)
    except Exception:
        logger.warning(
            "Unknown timezone %r in web data; falling back to %s",
            tz_name,
            DEFAULT_TIMEZONE,
        )
        return ZoneInfo(DEFAULT_TIMEZONE)


def _event_uid(site_key: str, web_event: Dict[str, Any]) -> str:
    """Build a stable UID for an event.

    Events carry no identifier of their own, so the UID is derived from the
    fields that identify the booking. Deriving it (rather than generating a
    random one) means a truck keeps the same calendar entry across refreshes;
    a renamed or rescheduled truck correctly becomes a new entry.
    """
    parts = [
        site_key,
        str(web_event.get("venue_key") or web_event.get("venue") or ""),
        str(web_event.get("date") or ""),
        str(web_event.get("title") or ""),
    ]
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()
    return f"{digest}@{UID_DOMAIN}"


def _build_description(web_event: Dict[str, Any]) -> Optional[str]:
    """Assemble the DESCRIPTION body, or None when there's nothing to say."""
    lines: List[str] = []

    description = web_event.get("description")
    if description:
        lines.append(str(description))

    if web_event.get("extraction_method") == "vision":
        lines.append("Vendor name extracted by AI image analysis.")

    return "\n".join(lines) if lines else None


def _build_vevent(
    web_event: Dict[str, Any],
    site_key: str,
    tz: ZoneInfo,
    site_name: str,
    public_url: str,
    max_timed_hours: Optional[float],
) -> Optional[CalendarEvent]:
    """Build one VEVENT, or None when the entry has no usable date."""
    event_date = _parse_iso(web_event.get("date"))
    if event_date is None:
        return None

    cal_event = CalendarEvent()
    cal_event.add("uid", _event_uid(site_key, web_event))
    # A discovery calendar must not reserve the subscriber's availability.
    # Deliberately add no VALARM; subscribers control their own reminders.
    cal_event.add("transp", "TRANSPARENT")

    title = str(web_event.get("title") or "Event")
    venue = str(web_event.get("venue") or web_event.get("location") or "")
    # Use the plain title, not the "vendor" key -- that one carries a 🖼️🤖
    # suffix which is a web-only affordance.
    cal_event.add("summary", f"{title} @ {venue}" if venue else title)

    start = _parse_iso(web_event.get("start_iso"))
    timing_note = ""
    all_day = start is None
    if start is not None:
        start_utc = _to_utc(start, tz)
        end = _parse_iso(web_event.get("end_iso"))
        if end is None:
            timing_note = (
                "End time estimated: shown as 3 hours after the published start."
            )
        end_utc = _to_utc(end, tz) if end else start_utc + DEFAULT_EVENT_DURATION
        if end_utc < start_utc:
            # A venue listing that closes past midnight parses as an earlier
            # clock time on the same day; roll it into the next day.
            end_utc += timedelta(days=1)
        duration_hours = (end_utc - start_utc).total_seconds() / 3600
        if max_timed_hours is not None and duration_hours > max_timed_hours:
            all_day = True
            reported_start = start_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
            reported_end = end_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
            timing_note = (
                "Hours uncertain - check the schedule. Shown as an all-day entry, "
                "not all-day service.\n"
                f"Reported hours (parsed): {reported_start} - {reported_end}."
            )
            if web_event.get("venue_url"):
                timing_note += f"\nSource: {web_event['venue_url']}"
            logger.warning(
                "Calendar hours uncertain for %s/%s (%s): start=%s end=%s; "
                "%.2f hours exceeds %.2f-hour threshold; using all-day entry",
                site_key,
                web_event.get("venue_key"),
                title,
                web_event.get("start_iso"),
                web_event.get("end_iso"),
                duration_hours,
                max_timed_hours,
            )
        else:
            cal_event.add("dtstart", start_utc)
            cal_event.add("dtend", end_utc)
        dtstamp = start_utc

    if all_day:
        if start is None:
            timing_note = "Hours not published."
        # Use the booking's local date, not its potentially erroneous start date.
        start_date = event_date.date()
        cal_event.add("dtstart", start_date)
        cal_event.add("dtend", start_date + timedelta(days=1))
        dtstamp = datetime(
            start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc
        )

    # DTSTAMP is deliberately derived from the event itself rather than
    # datetime.now(). RFC 5545 requires the property but its value is not
    # load-bearing for a published feed, and a "now" value would make the
    # generated file differ on every run -- which would defeat the no-op
    # short-circuit in main._deploy_with_github_auth and produce an empty
    # commit on every scheduled scrape. Do not change this to now().
    cal_event.add("dtstamp", dtstamp)

    if venue:
        cal_event.add("location", venue)

    description_parts = [
        part for part in (_build_description(web_event), timing_note) if part
    ]
    if public_url:
        description_parts.append(
            f"Curated by {site_name}.\n"
            f"See the latest schedule and explore more events:\n{public_url}\n\n"
            "Times may change; check before heading out."
        )
    if description_parts:
        cal_event.add("description", "\n\n".join(description_parts))

    venue_url = public_url or web_event.get("venue_url")
    if venue_url:
        cal_event.add("url", str(venue_url))

    return cal_event


def build_ics(web_data: Dict[str, Any]) -> bytes:
    """Render *web_data* as an RFC 5545 calendar.

    The output is deterministic: identical input produces byte-identical
    output, so an unchanged schedule does not create a spurious deploy.

    Args:
        web_data: The dict returned by ``main.generate_web_data``.

    Returns:
        The encoded ``.ics`` document.
    """
    site_key = str(web_data.get("site_key") or "events")
    site_name = str(web_data.get("site_name") or "Events")
    public_url = str(web_data.get("public_url") or "")
    tz_name = web_data.get("timezone") or DEFAULT_TIMEZONE
    tz = _resolve_timezone(tz_name)
    max_timed_hours = web_data.get("calendar_max_timed_hours")
    if max_timed_hours is not None:
        try:
            max_timed_hours = float(max_timed_hours)
            if not math.isfinite(max_timed_hours) or max_timed_hours <= 0:
                raise ValueError("Threshold must be finite and positive")
        except (TypeError, ValueError):
            logger.warning(
                "Ignoring invalid calendar duration threshold: %r",
                web_data.get("calendar_max_timed_hours"),
            )
            max_timed_hours = None

    cal = Calendar()
    cal.add("prodid", f"-//Around the Grounds//{site_key}//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", site_name)
    cal.add("x-wr-timezone", str(tz_name))
    cal.add("refresh-interval;value=duration", REFRESH_INTERVAL)
    cal.add("x-published-ttl", REFRESH_INTERVAL)

    # Events arrive already sorted by date/venue/time from the coordinator.
    for web_event in web_data.get("events") or []:
        cal_event = _build_vevent(
            web_event, site_key, tz, site_name, public_url, max_timed_hours
        )
        if cal_event is not None:
            cal.add_component(cal_event)

    ics: bytes = cal.to_ical()
    return ics
