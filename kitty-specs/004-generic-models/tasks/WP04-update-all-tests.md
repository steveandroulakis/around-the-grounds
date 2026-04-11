---
id: WP04
title: Update all tests
lane: planned
depends_on: [WP03]
feature: 004-generic-models
---

# WP04 — Update all tests

## Goal
Replace every `Brewery`/`FoodTruckEvent` reference across all 17 test files and shared fixtures so the full 196-test suite passes cleanly against the refactored production code.

## Context
- Upstream-first: this WP is a clean PR to around-the-grounds main
- Minimalism: change only what is listed, nothing else
- Branch: `004-generic-models`

## Subtasks
- [ ] Add `make_aware(dt)` helper to `tests/conftest.py`
- [ ] Update `sample_brewery()` → `sample_venue()` fixture in conftest.py
- [ ] Update `sample_food_truck_event()` → `sample_event()` fixture in conftest.py
- [ ] Update all 17 test files: field renames, tz-aware datetimes, Venue/Event types

## Files to change
- `tests/conftest.py`:
  - Add helper: `def make_aware(dt): return dt.replace(tzinfo=ZoneInfo("America/Los_Angeles"))`
  - `sample_brewery()` → `sample_venue()` returning `Venue(..., source_type="html")`
  - `sample_food_truck_event()` → `sample_event()` returning `Event(...)` with tz-aware `datetime_start`
- `tests/unit/test_models.py` — `TestBrewery`→`TestVenue` (add `source_type` validation); `TestFoodTruckEvent`→`TestEvent` (add tz-aware datetime tests)
- `tests/unit/test_base_parser.py` — `parser.brewery`→`parser.venue`; field mutation assertions updated
- `tests/unit/test_haiku_generator.py` — `FoodTruckEvent(...)`→`Event(...)` tz-aware; field renames
- `tests/unit/test_parser_timezone_integration.py` — `Brewery(...)`→`Venue(..., source_type="html")`
- `tests/integration/test_coordinator.py` — `Brewery(...)`→`Venue(...)`; `FoodTruckEvent(...)`→`Event(...)` tz-aware; `ScrapingError.brewery`→`.venue`
- `tests/integration/test_cli.py` — `FoodTruckEvent(...)`→`Event(...)`; `ai_generated_name=True`→`extraction_method="ai-vision"`
- `tests/integration/test_haiku_integration.py` — field renames + tz-aware datetimes
- `tests/parsers/test_stoup_ballard.py` — `brewery_key`→`venue_key`; `brewery_name`→`venue_name`; `food_truck_name`→`title`
- `tests/parsers/test_bale_breaker.py` — same field renames
- `tests/parsers/test_chucks_greenwood.py` — same field renames
- `tests/parsers/test_obec_brewing.py` — same field renames
- `tests/parsers/test_salehs_corner.py` — field renames; `not event.ai_generated_name`→`event.extraction_method != "ai-vision"`
- `tests/parsers/test_urban_family.py` — same field renames
- `tests/parsers/test_wheelie_pop.py` — same field renames
- `tests/temporal/test_activities.py` — wire dict keys updated; `Brewery(...)`→`Venue(...)`
- `tests/test_error_handling.py` — `Brewery(...)`→`Venue(..., source_type="html")`

## Acceptance criteria
- `uv run python -m pytest` — all 196 tests pass (zero deletions)

## Notes
- **High severity: test fixtures use naive datetimes** — `conftest.py` lines 27-34 and `test_coordinator.py` lines 44-62 construct naive datetimes. All `FoodTruckEvent(date=...)` usages must become `Event(datetime_start=make_aware(...))`. Missing even one will cause a `ValueError` at test runtime.
- **`test_salehs_corner.py`** has two assertions like `not event.ai_generated_name` (lines 142, 369) — change to `event.extraction_method != "ai-vision"`.
- **Zero test deletions**: the constraint from the spec is that no tests are removed. Every existing test must be updated in place to use the new types.
- `make_aware` must be defined in `conftest.py` so it is available across all test files via import or direct use.
