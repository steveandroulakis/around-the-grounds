# Data Model: 004 — Generic Models

## Field mapping: old models → new models

### Brewery → Venue

| Old field | Old type | New field | New type | Notes |
|---|---|---|---|---|
| `key` | `str` | `key` | `str` | Unchanged |
| `name` | `str` | `name` | `str` | Unchanged |
| `url` | `str` | `url` | `str` | Unchanged |
| `parser_config` | `Optional[Dict[str, Any]]` | `parser_config` | `Dict[str, Any]` | Non-optional; always a dict |
| _(none)_ | — | `source_type` | `str` | **New required field.** Default `"html"` for all existing venues. Valid: `"html"`, `"ical"`, `"api"`. |
| _(none)_ | — | `timezone` | `Optional[str]` | New optional. ZoneInfo name. Not populated in this spec. |
| _(none)_ | — | `location` | `Optional[Location]` | New optional. Not populated in this spec. |

### FoodTruckEvent → Event

| Old field | Old type | New field | New type | Notes |
|---|---|---|---|---|
| `brewery_key` | `str` | `venue_key` | `str` | Renamed |
| `brewery_name` | `str` | `venue_name` | `str` | Renamed |
| `food_truck_name` | `str` | `title` | `str` | Renamed |
| `date` | `datetime` (naive, midnight) | _(absorbed)_ | — | Removed. Use `datetime_start.date()` instead. |
| `start_time` | `Optional[datetime]` (naive) | `datetime_start` | `datetime` (tz-aware) | **Required, tz-aware.** If no start time, use midnight of the date. |
| `end_time` | `Optional[datetime]` (naive) | `datetime_end` | `Optional[datetime]` (tz-aware) | Optional, tz-aware if present. |
| `description` | `Optional[str]` | `description` | `Optional[str]` | Unchanged |
| `ai_generated_name` | `bool` | `extraction_method` | `str` | `False` → `"html"` or `"api"`. `True` → `"ai-vision"`. |
| _(none)_ | — | `url` | `Optional[str]` | New optional. Not populated in this spec. |
| _(none)_ | — | `categories` | `List[str]` | New optional list. Not populated in this spec. |
| _(none)_ | — | `cost` | `Optional[str]` | New optional. Not populated in this spec. |
| _(none)_ | — | `sold_out` | `bool` | New optional. Defaults `False`. |
| _(none)_ | — | `location` | `Optional[Location]` | New optional. Not populated in this spec. |

### New model: Location

All fields optional. Not instantiated by any parser in this spec.

| Field | Type | Notes |
|---|---|---|
| `address` | `Optional[str]` | Street address |
| `lat` | `Optional[float]` | Latitude |
| `lng` | `Optional[float]` | Longitude |
| `timezone` | `Optional[str]` | ZoneInfo name e.g. `"America/Los_Angeles"` |

### New model: VenueList

Added to the model layer in this spec. Not instantiated in production code until spec 006.

| Field | Type | Notes |
|---|---|---|
| `list_name` | `str` | Human-readable name |
| `venues` | `List[Venue]` | At least one required |
| `target_repo` | `str` | Git repo URL for deployment |
| `target_branch` | `str` | Defaults `"main"` |
| `template_dir` | `Optional[str]` | Path to HTML template directory |

---

## Validation rules (`__post_init__`)

### Venue
- `source_type` must be in `{"html", "ical", "api"}`.
  Raises `ValueError: Invalid source_type '{value}' for venue '{key}'`.

### Event
- `datetime_start.tzinfo` must not be `None`.
  Raises `ValueError: Event.datetime_start must be timezone-aware, got naive datetime for '{title}'`.
- If `datetime_end` is not `None`, `datetime_end.tzinfo` must not be `None`.
  Raises `ValueError: Event.datetime_end must be timezone-aware if provided`.

### VenueList
- `venues` must not be empty. Raises `ValueError`.
- All `venue.key` values must be unique. Raises `ValueError` listing duplicates.

---

## JSON output shape change (data.json)

The `data.json` output produced by `generate_web_data()` in `main.py` is **backwards-compatible**.
All existing field names and value formats are preserved. The frontend requires no changes.

### What changes internally (source fields only)

| JSON key | Old source | New source | Value format change? |
|---|---|---|---|
| `"date"` | `event.date.isoformat()` | `event.datetime_start.date().isoformat()` | No (`YYYY-MM-DD`) |
| `"vendor"` | `event.food_truck_name` | `event.title` | No |
| `"location"` | `event.brewery_name` | `event.venue_name` | No |
| `"start_time"` | `event.start_time` | `event.datetime_start` | No |
| `"end_time"` | `event.end_time` | `event.datetime_end` | No |
| `"start_time_raw"` | `event.start_time` | `event.datetime_start` | No |
| `"end_time_raw"` | `event.end_time` | `event.datetime_end` | No |
| `"description"` | `event.description` | `event.description` | No |
| `"timezone"` | hardcoded `"PT"` | hardcoded `"PT"` | No |
| `"extraction_method"` | set when `event.ai_generated_name` | set when `event.extraction_method == "ai-vision"` | No |

### Temporal wire format change

The Temporal activities serialization dict (`_serialize_event`) changes field names.
This is an **internal wire format** — not exposed to the frontend or public API.
Any existing Temporal workflow run-history that contains the old field names will not be
affected as Temporal replays use the activity code at replay time.
