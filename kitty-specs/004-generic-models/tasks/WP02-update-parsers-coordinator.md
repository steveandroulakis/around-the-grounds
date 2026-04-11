---
id: WP02
title: Update coordinator + base parser + all 7 parsers
lane: planned
depends_on: [WP01]
feature: 004-generic-models
---

# WP02 — Update coordinator + base parser + all 7 parsers

## Goal
Make the scraping infrastructure speak `Venue`/`Event` end-to-end: update `timezone_utils.py`, `base.py`, all 7 concrete parsers, and `coordinator.py` so that no `FoodTruckEvent` or `Brewery` references remain in `parsers/` or `scrapers/`.

## Context
- Upstream-first: this WP is a clean PR to around-the-grounds main
- Minimalism: change only what is listed, nothing else
- Branch: `004-generic-models`

## Subtasks
- [ ] Add `utc_to_pacific_aware()` to `around_the_grounds/utils/timezone_utils.py`
- [ ] Update `around_the_grounds/parsers/base.py` type signatures (10 atomic edits)
- [ ] Update `stoup_ballard.py`: self.venue, Event construction, tz-aware datetimes
- [ ] Update `bale_breaker.py`: self.venue, Event construction, remove tzinfo strip
- [ ] Update `urban_family.py`: explicit __init__, self.venue, Event, remove tzinfo strip
- [ ] Update `obec_brewing.py`: self.venue, Event, now_in_pacific()
- [ ] Update `chucks_greenwood.py`: self.venue, Event, PACIFIC_TZ attach
- [ ] Update `salehs_corner.py`: explicit __init__, self.venue, Event, utc_to_pacific_aware
- [ ] Update `wheelie_pop.py`: self.venue, Event, utc_to_pacific_aware, _event_key fix
- [ ] Update `around_the_grounds/scrapers/coordinator.py` (Venue/Event types, _scrape_venue rename)

## Files to change
- `around_the_grounds/utils/timezone_utils.py` — add `utc_to_pacific_aware(utc_dt)` alongside existing `utc_to_pacific_naive`
- `around_the_grounds/parsers/base.py` — update imports and type signatures: `Brewery`→`Venue`, `FoodTruckEvent`→`Event`; field refs: `brewery_key`→`venue_key`, `brewery_name`→`venue_name`, `food_truck_name`→`title`, `date`→`datetime_start`
- `around_the_grounds/parsers/stoup_ballard.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, attach `PACIFIC_TZ` to naive datetimes
- `around_the_grounds/parsers/bale_breaker.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, remove `.replace(tzinfo=None)`, fallback uses `datetime.now(PACIFIC_TZ)`
- `around_the_grounds/parsers/urban_family.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, remove `.replace(tzinfo=None)` in `_parse_time_string`, `ai_generated_name=True`→`extraction_method="ai-vision"`
- `around_the_grounds/parsers/obec_brewing.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, `now_in_pacific_naive()`→`now_in_pacific()`
- `around_the_grounds/parsers/chucks_greenwood.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, add `.replace(tzinfo=PACIFIC_TZ)` after `parse_date_with_pacific_context()`
- `around_the_grounds/parsers/salehs_corner.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, `utc_to_pacific_naive`→`utc_to_pacific_aware`, `extraction_method="api"`
- `around_the_grounds/parsers/wheelie_pop.py` — `self.brewery`→`self.venue`, `FoodTruckEvent`→`Event`, `utc_to_pacific_naive`→`utc_to_pacific_aware`, `_event_key`: `event.date`→`event.datetime_start.strftime('%Y-%m-%d')`
- `around_the_grounds/scrapers/coordinator.py` — `Brewery`→`Venue`, `FoodTruckEvent`→`Event`, `_scrape_brewery`→`_scrape_venue`, `event.date.date()`→`event.datetime_start.date()`, sort key updated, hardcoded `timezone(timedelta(hours=-8))`→`PACIFIC_TZ`

## Acceptance criteria
- All parser imports clean
- No `FoodTruckEvent` or `Brewery` imports in `parsers/` or `scrapers/`
- `grep -r "FoodTruckEvent\|import Brewery\|from.*brewery import" around_the_grounds/parsers/ around_the_grounds/scrapers/` returns zero matches

## Notes
- **Timezone promotion**: All 7 parsers currently produce timezone-naive datetimes. `Event.__post_init__` raises `ValueError` if `datetime_start.tzinfo is None`. Each parser has a specific fix (see plan.md WP02 timezone table).
- **`ai_generated_name` → `extraction_method`**: `False`→`"html"`, `True`→`"ai-vision"`, API-sourced (salehs_corner)→`"api"`.
- **`bale_breaker.py` fallback**: `date=datetime.now()` must become `datetime_start=datetime.now(PACIFIC_TZ)` — this is a medium-severity risk if missed.
- **`wheelie_pop.py` `_event_key`**: accesses `event.date` which no longer exists; must change to `event.datetime_start.strftime('%Y-%m-%d')`.
- **`coordinator.py` `_filter_and_sort_events`**: replace hardcoded `timezone(timedelta(hours=-8))` with imported `PACIFIC_TZ` to avoid DST issues.
- Test assertions in `tests/` are updated in WP04, not here. Tests may fail between WP02 and WP04 — that is expected.
