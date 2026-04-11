# Implementation Plan: 004 — Generic Models

**Branch**: `004-generic-models` | **Date**: 2026-02-25 | **Spec**: [spec.md](spec.md)

## Summary

Replace `Brewery` and `FoodTruckEvent` with ventr's generic `Venue`, `Event`, `Location`, and
`VenueList` models throughout the around-the-grounds codebase. This is a pure type-substitution
refactor — no parser logic, registry pattern, or file structure changes. The goal is zero
behaviour change; only the type names and field names move.

## Technical Context

- **Language/Version**: Python 3.8+ (`zoneinfo` with `backports.zoneinfo` fallback)
- **Primary Dependencies**: aiohttp, beautifulsoup4, anthropic, temporalio
- **Testing**: pytest, 196 tests — all must pass after refactor
- **Constraints**: Zero test deletions; no parser logic or structure changes

## Project Structure

```
around_the_grounds/
├── models/
│   ├── __init__.py          (update exports)
│   ├── event.py             (NEW — copied from ventr)
│   ├── venue.py             (NEW — copied from ventr)
│   ├── venue_list.py        (NEW — copied from ventr)
│   ├── brewery.py           (keep through WP04, delete in WP05)
│   └── schedule.py          (keep through WP04, delete in WP05)
├── parsers/
│   ├── base.py              (type signatures only)
│   ├── stoup_ballard.py     (self.brewery→self.venue + Event construction)
│   ├── bale_breaker.py      (same)
│   ├── urban_family.py      (same + ai-vision extraction_method)
│   ├── obec_brewing.py      (same)
│   ├── chucks_greenwood.py  (same)
│   ├── salehs_corner.py     (same + api extraction_method)
│   └── wheelie_pop.py       (same)
├── scrapers/
│   └── coordinator.py       (type signatures + _scrape_brewery→_scrape_venue)
├── utils/
│   ├── timezone_utils.py    (add utc_to_pacific_aware helper)
│   └── haiku_generator.py   (field renames)
├── temporal/
│   └── activities.py        (wire format update)
└── main.py                  (field renames + source_type="html" default)
```

## Work Packages

### WP01 — Copy ventr models into ATG + update `__init__.py`

**Goal**: Add new model files. After this WP, old and new models are importable simultaneously.
No other code changes.

**Files to create/modify**:

1. `around_the_grounds/models/event.py` — Create. Copy `Location` and `Event` verbatim
   from `ventr/ventr/models/event.py`. No import path changes needed.

2. `around_the_grounds/models/venue.py` — Create. Copy `Venue` verbatim from
   `ventr/ventr/models/venue.py`. Change import:
   `from ventr.models.event import Location` → `from .event import Location`

3. `around_the_grounds/models/venue_list.py` — Create. Copy `VenueList` verbatim from
   `ventr/ventr/models/venue_list.py`. Change import:
   `from ventr.models.venue import Venue` → `from .venue import Venue`

4. `around_the_grounds/models/__init__.py` — Add new exports alongside existing:
   ```python
   from .brewery import Brewery
   from .schedule import FoodTruckEvent
   from .event import Event, Location
   from .venue import Venue
   from .venue_list import VenueList

   __all__ = ["Brewery", "FoodTruckEvent", "Event", "Location", "Venue", "VenueList"]
   ```

**Testable**: `python -c "from around_the_grounds.models import Venue, Event, Location, VenueList"`
**Depends on**: nothing
**Blocks**: WP02, WP03, WP04

---

### WP02 — Update coordinator + base parser + all 7 parsers

**Goal**: Make the scraping infrastructure speak `Venue`/`Event` end-to-end.

#### `around_the_grounds/utils/timezone_utils.py` — New helper (do this first)

Add alongside existing `utc_to_pacific_naive`:
```python
def utc_to_pacific_aware(utc_dt: datetime) -> datetime:
    """Convert UTC datetime to Pacific timezone, preserving tzinfo."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
    return utc_dt.astimezone(PACIFIC_TZ)
```

#### `around_the_grounds/parsers/base.py`

- Import: `from ..models import Brewery, FoodTruckEvent` → `from ..models import Venue, Event`
- `__init__`: `brewery: Brewery` → `venue: Venue`; `self.brewery` → `self.venue`
- `parse()` return: `List[FoodTruckEvent]` → `List[Event]`
- `validate_event()`: param `FoodTruckEvent` → `Event`; field refs:
  - `event.brewery_key` → `event.venue_key`
  - `event.brewery_name` → `event.venue_name`
  - `event.food_truck_name` → `event.title`
  - `event.date` → `event.datetime_start`
- `filter_valid_events()`: list types updated

#### All 7 parsers — `self.brewery` → `self.venue` + timezone promotion

**`self.brewery.*` → `self.venue.*` sweep** (occurrence counts):
stoup_ballard.py (7), bale_breaker.py (6), urban_family.py (7),
obec_brewing.py (3), chucks_greenwood.py (3), salehs_corner.py (4), wheelie_pop.py (3)

**Timezone promotion strategy per parser**:

| Parser | Current behaviour | Change required |
|---|---|---|
| `stoup_ballard.py` | `datetime(year, month, day)` naive | `.replace(tzinfo=PACIFIC_TZ)` after constructing datetime |
| `obec_brewing.py` | `now_in_pacific_naive()` — strips tz | Use `now_in_pacific()` (keeps tzinfo) |
| `chucks_greenwood.py` | `parse_date_with_pacific_context(...)` naive | Add `.replace(tzinfo=PACIFIC_TZ)` after call |
| `bale_breaker.py` | `.replace(tzinfo=None)` strips tz | Remove the `.replace(tzinfo=None)` |
| `urban_family.py` | `.replace(tzinfo=None)` in `_parse_time_string` | Remove `.replace(tzinfo=None)` |
| `salehs_corner.py` | `utc_to_pacific_naive(dt)` | Use `utc_to_pacific_aware(dt)` |
| `wheelie_pop.py` | `utc_to_pacific_naive(parsed)` | Use `utc_to_pacific_aware(parsed)` |

**`FoodTruckEvent` → `Event` construction pattern**:
```python
# Before
FoodTruckEvent(
    brewery_key=self.brewery.key,
    brewery_name=self.brewery.name,
    food_truck_name=truck_name,
    date=current_date,
    start_time=start_time,
    end_time=end_time,
    ai_generated_name=False,
)

# After
Event(
    venue_key=self.venue.key,
    venue_name=self.venue.name,
    title=truck_name,
    datetime_start=(start_time or current_date).replace(tzinfo=PACIFIC_TZ),
    datetime_end=end_time.replace(tzinfo=PACIFIC_TZ) if end_time else None,
    extraction_method="html",
)
```

**`ai_generated_name` → `extraction_method`**:
- `ai_generated_name=False` → `extraction_method="html"`
- `ai_generated_name=True` (UrbanFamily) → `extraction_method="ai-vision"`
- `salehs_corner.py` API-sourced → `extraction_method="api"`

**Special cases**:
- `wheelie_pop.py` `_event_key()`: `event.date` → `event.datetime_start.strftime('%Y-%m-%d')`
- `bale_breaker.py` fallback event: `date=datetime.now()` → `datetime_start=datetime.now(PACIFIC_TZ)`

#### `around_the_grounds/scrapers/coordinator.py`

- Import: `from ..models import Brewery, FoodTruckEvent` → `from ..models import Venue, Event`
- `ScrapingError`: `brewery: Brewery` → `venue: Venue`; `self.brewery` → `self.venue`
- `scrape_all()`: `breweries: List[Brewery]` → `venues: List[Venue]`; return `List[Event]`
- `_scrape_brewery()` → rename `_scrape_venue()`; all `brewery` params → `venue`
- `_filter_and_sort_events()`:
  - `event.date.date()` → `event.datetime_start.date()`
  - Sort key: `(x.date, x.start_time or x.date)` → `(x.datetime_start, x.datetime_start)`
  - Hardcoded `timezone(timedelta(hours=-8))` → `PACIFIC_TZ`

**Testable**: All existing parser tests pass (with field assertions updated in WP04)
**Depends on**: WP01
**Blocks**: WP03, WP04

---

### WP03 — Update `main.py`, `haiku_generator.py`, `activities.py`

**Goal**: Update output/deployment pipeline to use `Event`/`Venue`.

#### `around_the_grounds/main.py`

- `load_brewery_config()`: `Brewery(...)` → `Venue(..., source_type="html", ...)`
  - Hard-code `source_type="html"` — `breweries.json` has no such field (spec 006 extension point)
- `format_events_output()`, `_generate_haiku_for_today()`, `generate_web_data()`:
  - `event.date` → `event.datetime_start.date()`
  - `event.food_truck_name` → `event.title`
  - `event.brewery_name` → `event.venue_name`
  - `event.start_time` → `event.datetime_start`; `event.end_time` → `event.datetime_end`
  - `event.ai_generated_name` → `event.extraction_method == "ai-vision"`
- Variable rename: `breweries` → `venues` throughout `async_main()`

**Note**: `data.json` output field names (`vendor`, `location`, `date`, `start_time`, etc.)
are **unchanged** — only the source fields change. Frontend requires no updates.

#### `around_the_grounds/utils/haiku_generator.py`

- Import: `FoodTruckEvent` → `Event`
- All method signatures updated to `List[Event]`
- `selected_event.food_truck_name` → `selected_event.title`
- `selected_event.brewery_name` → `selected_event.venue_name`
- `event.date.date()` → `event.datetime_start.date()`
- `f"- {event.food_truck_name} at {event.brewery_name}"` → `f"- {event.title} at {event.venue_name}"`

#### `around_the_grounds/temporal/activities.py`

- `_serialize_event()` wire format:
  ```
  "brewery_key"       → "venue_key"
  "brewery_name"      → "venue_name"
  "food_truck_name"   → "title"
  "date"              → "datetime_start"  (isoformat with tz offset)
  "start_time"        → (removed, collapsed into datetime_start)
  "end_time"          → "datetime_end"    (isoformat or null)
  "ai_generated_name" → "extraction_method"
  ```
- `_serialize_error`: `error.brewery.name` → `error.venue.name`
- `scrape_food_trucks` / `scrape_single_brewery`: `Brewery(...)` → `Venue(..., source_type="html")`
- `generate_web_data` — `Event` reconstruction from wire dict:
  ```python
  Event(
      venue_key=event_data["venue_key"],
      venue_name=event_data["venue_name"],
      title=event_data["title"],
      datetime_start=datetime.fromisoformat(event_data["datetime_start"]),
      datetime_end=datetime.fromisoformat(event_data["datetime_end"]) if event_data["datetime_end"] else None,
      description=event_data["description"],
      extraction_method=event_data["extraction_method"],
  )
  ```

**Testable**: CLI, haiku, and activities tests pass (with field updates from WP04)
**Depends on**: WP01, WP02
**Blocks**: WP04, WP05

---

### WP04 — Update all tests

**Goal**: Replace every `Brewery`/`FoodTruckEvent` reference in tests.

#### `tests/conftest.py` key changes
- `sample_brewery()` → `sample_venue()` returning `Venue(..., source_type="html")`
- `sample_food_truck_event()` → `sample_event()` returning `Event(...)` with tz-aware datetimes
- Add `make_aware(dt)` helper: `return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))`

#### Per-file summary (17 test files)

| File | Key changes |
|---|---|
| `tests/unit/test_models.py` | `TestBrewery`→`TestVenue` (add source_type validation tests); `TestFoodTruckEvent`→`TestEvent` (add tz-aware datetime tests) |
| `tests/unit/test_base_parser.py` | `parser.brewery`→`parser.venue`; field mutation assertions updated |
| `tests/unit/test_haiku_generator.py` | `FoodTruckEvent(...)` → `Event(...)` tz-aware; field renames |
| `tests/unit/test_parser_timezone_integration.py` | `Brewery(...)` → `Venue(..., source_type="html")` |
| `tests/integration/test_coordinator.py` | `Brewery(...)` → `Venue(...)`; `FoodTruckEvent(...)` → `Event(...)` tz-aware; `ScrapingError.brewery` → `.venue` |
| `tests/integration/test_cli.py` | `FoodTruckEvent(...)` → `Event(...)`; `ai_generated_name=True` → `extraction_method="ai-vision"` |
| `tests/integration/test_haiku_integration.py` | Field renames + tz-aware datetimes |
| `tests/parsers/test_stoup_ballard.py` | `brewery_key`→`venue_key`; `brewery_name`→`venue_name`; `food_truck_name`→`title` |
| `tests/parsers/test_bale_breaker.py` | Same field renames |
| `tests/parsers/test_chucks_greenwood.py` | Same field renames |
| `tests/parsers/test_obec_brewing.py` | Same field renames |
| `tests/parsers/test_salehs_corner.py` | `not event.ai_generated_name` → `event.extraction_method != "ai-vision"` |
| `tests/parsers/test_urban_family.py` | Same field renames |
| `tests/parsers/test_wheelie_pop.py` | Same field renames |
| `tests/temporal/test_activities.py` | Wire dict keys updated; `Brewery(...)` → `Venue(...)` |
| `tests/test_error_handling.py` | `Brewery(...)` → `Venue(..., source_type="html")` |

**Testable**: `uv run python -m pytest` — all 196 tests pass
**Depends on**: WP01, WP02, WP03
**Blocks**: WP05

---

### WP05 — Remove deprecated models

**Files to delete**:
- `around_the_grounds/models/brewery.py`
- `around_the_grounds/models/schedule.py`

**`__init__.py` final state**:
```python
from .event import Event, Location
from .venue import Venue
from .venue_list import VenueList

__all__ = ["Event", "Location", "Venue", "VenueList"]
```

**Verify clean**: `grep -r "FoodTruckEvent\|from.*brewery\|import.*Brewery" around_the_grounds/`
returns zero matches.

**Testable**: `uv run python -m pytest` — all tests pass with old model files gone.
**Depends on**: WP04
**Blocks**: nothing

---

## Dependency Order

```
WP01 (copy models)
  └─→ WP02 (coordinator + parsers)
        └─→ WP03 (main.py + haiku + activities)
              └─→ WP04 (tests)
                    └─→ WP05 (delete old models)
```

WP03's `main.py` and `haiku_generator.py` changes can begin after WP01.
WP03's `activities.py` change must wait for WP02.

---

## Timezone Handling Detail

All 7 parsers produce timezone-naive datetimes today. `Event.__post_init__` raises `ValueError`
if `datetime_start.tzinfo is None`. The fix is per-parser (see WP02 table above).

**Fallback timezone for all existing parsers**: `ZoneInfo("America/Los_Angeles")`

**New helper** in `timezone_utils.py`: `utc_to_pacific_aware()` — keeps tzinfo after UTC→Pacific
conversion. The existing `utc_to_pacific_naive()` stays until WP05 cleanup.

**`_filter_and_sort_events` note**: Replace hardcoded `timezone(timedelta(hours=-8))` with
`PACIFIC_TZ`. Date comparisons use `event.datetime_start.date()`.

---

## Risk Register

| Risk | Severity | Location | Mitigation |
|---|---|---|---|
| Test fixtures use naive datetimes | High | `conftest.py` L27-34; `test_coordinator.py` L44-62; 16 other files | Add `make_aware(dt)` to `conftest.py`; apply everywhere |
| `activities.py` serialize+deserialize must update atomically | High | `activities.py` L32-43, L140-158 | Update both sides in WP03 together; wire keys must match exactly |
| `wheelie_pop.py` `_event_key` accesses `event.date` | Medium | `wheelie_pop.py` L229-235 | Change to `event.datetime_start.strftime(...)` in WP02 |
| `bale_breaker.py` fallback event uses naive `datetime.now()` | Medium | `bale_breaker.py` L221-228 | Use `datetime.now(PACIFIC_TZ)` in WP02 |
| `Venue.source_type` validation rejects venues from `breweries.json` | High | `main.py` L43-50; `activities.py` L82-90 | Hard-code `source_type="html"` in config loader; document as spec 006 point |
| Tests asserting `not event.ai_generated_name` | Medium | `test_salehs_corner.py` L142, L369 | Change to `event.extraction_method != "ai-vision"` |
| `VenueList` importable but not used in production | Info | `main.py` | Defer full VenueList config loader to spec 006 |
