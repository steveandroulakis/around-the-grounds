# Tasks: 005 — Adapter Interface Update

## WP01 — Update BaseParser type signatures
lane: planned
depends_on: []
blocked_by_feature: 004-generic-models

### Subtasks
- [ ] Update import: `Brewery, FoodTruckEvent` → `Venue, Event` in base.py
- [ ] Update `__init__`: `brewery: Brewery` → `venue: Venue`; `self.brewery` → `self.venue`
- [ ] Update `parse()` return type: `List[FoodTruckEvent]` → `List[Event]`
- [ ] Update `validate_event()` signature and 4 field references
- [ ] Update `filter_valid_events()` list types

### Acceptance
- `python -c "from around_the_grounds.parsers.base import BaseParser"` — no error
- `parsers/registry.py` diff is empty

---

## WP02 — Update all 7 parsers
lane: planned
depends_on: [WP01]

### Subtasks
- [ ] `stoup_ballard.py`: import, self.venue sweep (7 occurrences), Event construction, tz-aware
- [ ] `bale_breaker.py`: import, self.venue sweep (6), Event construction, remove tzinfo strips, fallback event
- [ ] `urban_family.py`: import, explicit __init__ override, self.venue sweep (7), Event, remove tzinfo strip, extraction_method
- [ ] `obec_brewing.py`: import, now_in_pacific, self.venue sweep (3), Event construction
- [ ] `chucks_greenwood.py`: import, PACIFIC_TZ, self.venue sweep (3), Event construction
- [ ] `salehs_corner.py`: import, explicit __init__ override, utc_to_pacific_aware, self.venue sweep (4), Event, extraction_method="api"
- [ ] `wheelie_pop.py`: import, utc_to_pacific_aware, self.venue sweep (3), Event, _event_key fix, type annotations

### Acceptance
- `grep -r "FoodTruckEvent\|import.*Brewery\|from.*Brewery" around_the_grounds/parsers/` → zero matches
- All datetime_start values are tz-aware
- `salehs_corner.py` uses `extraction_method="api"`
- `parsers/registry.py` diff is empty

---

## WP03 — FR4 audit
lane: planned
depends_on: [WP02]

### Subtasks
- [ ] Run: `grep -r "FoodTruckEvent" around_the_grounds/parsers/` → must be zero
- [ ] Run: `grep -r "from.*Brewery\|import.*Brewery" around_the_grounds/parsers/` → must be zero
- [ ] Confirm `parsers/registry.py` is unchanged

### Acceptance
- Both greps return zero results
- `uv run python -m pytest tests/parsers/` passes
