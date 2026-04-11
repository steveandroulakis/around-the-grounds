---
id: WP03
title: Update main.py, haiku_generator.py, activities.py
lane: planned
depends_on: [WP02]
feature: 004-generic-models
---

# WP03 — Update main.py, haiku_generator.py, activities.py

## Goal
Update the output and deployment pipeline (`main.py`, `haiku_generator.py`, `activities.py`) to use `Event`/`Venue` types so the full application runs end-to-end without any `FoodTruckEvent` or `Brewery` references outside of `models/`.

## Context
- Upstream-first: this WP is a clean PR to around-the-grounds main
- Minimalism: change only what is listed, nothing else
- Branch: `004-generic-models`

## Subtasks
- [ ] Update `around_the_grounds/main.py`: load_brewery_config return type, field renames throughout
- [ ] Update `around_the_grounds/utils/haiku_generator.py`: field renames
- [ ] Update `around_the_grounds/temporal/activities.py`: wire format update (serialize/deserialize)

## Files to change
- `around_the_grounds/main.py`:
  - `load_brewery_config()` return type `List[Brewery]` → `List[Venue]`; hard-code `source_type="html"` when constructing `Venue` from `breweries.json` (field not yet in config — spec 006 extension point)
  - `format_events_output()`, `_generate_haiku_for_today()`, `generate_web_data()`:
    - `event.date` → `event.datetime_start.date()`
    - `event.food_truck_name` → `event.title`
    - `event.brewery_name` → `event.venue_name`
    - `event.start_time` → `event.datetime_start`
    - `event.end_time` → `event.datetime_end`
    - `event.ai_generated_name` → `event.extraction_method == "ai-vision"`
  - Variable rename: `breweries` → `venues` throughout `async_main()`
- `around_the_grounds/utils/haiku_generator.py`:
  - Import `FoodTruckEvent` → `Event`
  - All method signatures updated to `List[Event]`
  - `selected_event.food_truck_name` → `selected_event.title`
  - `selected_event.brewery_name` → `selected_event.venue_name`
  - `event.date.date()` → `event.datetime_start.date()`
  - `f"- {event.food_truck_name} at {event.brewery_name}"` → `f"- {event.title} at {event.venue_name}"`
- `around_the_grounds/temporal/activities.py`:
  - `_serialize_event()` wire keys: `brewery_key`→`venue_key`, `brewery_name`→`venue_name`, `food_truck_name`→`title`, `date`+`start_time`→`datetime_start` (isoformat with tz), `end_time`→`datetime_end`, `ai_generated_name`→`extraction_method`
  - `_serialize_error`: `error.brewery.name` → `error.venue.name`
  - `scrape_food_trucks` / `scrape_single_brewery`: `Brewery(...)` → `Venue(..., source_type="html")`
  - `generate_web_data`: reconstruct `Event` from updated wire dict keys

## Acceptance criteria
- `uv run around-the-grounds --help` runs without import errors
- Haiku generator tests pass
- `data.json` output field names (`vendor`, `location`, `date`, `start_time`, etc.) are unchanged — frontend requires no updates

## Notes
- **`activities.py` serialize+deserialize must update atomically** (high severity): both `_serialize_event()` and the `Event(...)` reconstruction in `generate_web_data` use the same wire dict keys. If they diverge the Temporal workflow will silently produce wrong data. Update both sides in this WP together.
- **`source_type` validation**: `Venue.source_type` may reject venues loaded from `breweries.json` because that config has no such field. Hard-coding `source_type="html"` in `load_brewery_config()` and the activities `Venue(...)` constructors is the correct fix; full config support is deferred to spec 006.
- **data.json unchanged**: the web frontend reads `vendor`, `location`, `date`, `start_time`, etc. — those output field names must remain identical. Only the internal Python field names change.
