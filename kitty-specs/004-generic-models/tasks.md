# Tasks: 004 — Generic Models

## WP01 — Copy ventr models into ATG
lane: planned
depends_on: []

### Subtasks
- [ ] Create `around_the_grounds/models/event.py` (copy from ventr, fix import path)
- [ ] Create `around_the_grounds/models/venue.py` (copy from ventr, fix import path)
- [ ] Create `around_the_grounds/models/venue_list.py` (copy from ventr, fix import path)
- [ ] Update `around_the_grounds/models/__init__.py` to export new models alongside old

### Acceptance
- `python -c "from around_the_grounds.models import Venue, Event, Location, VenueList"` succeeds
- Old models still importable (no breakage)

---

## WP02 — Update coordinator + base parser + all 7 parsers
lane: planned
depends_on: [WP01]

### Subtasks
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

### Acceptance
- All parser imports clean
- No `FoodTruckEvent` or `Brewery` imports in parsers/ or scrapers/

---

## WP03 — Update main.py, haiku_generator.py, activities.py
lane: planned
depends_on: [WP02]

### Subtasks
- [ ] Update `around_the_grounds/main.py`: load_brewery_config return type, field renames throughout
- [ ] Update `around_the_grounds/utils/haiku_generator.py`: field renames
- [ ] Update `around_the_grounds/temporal/activities.py`: wire format update (serialize/deserialize)

### Acceptance
- `uv run around-the-grounds --help` runs without import errors
- Haiku generator tests pass

---

## WP04 — Update all tests
lane: planned
depends_on: [WP03]

### Subtasks
- [ ] Add `make_aware(dt)` helper to `tests/conftest.py`
- [ ] Update `sample_brewery()` → `sample_venue()` fixture in conftest.py
- [ ] Update `sample_food_truck_event()` → `sample_event()` fixture in conftest.py
- [ ] Update all 17 test files: field renames, tz-aware datetimes, Venue/Event types

### Acceptance
- `uv run python -m pytest` — all tests pass

---

## WP05 — Remove deprecated models
lane: planned
depends_on: [WP04]

### Subtasks
- [ ] Delete `around_the_grounds/models/brewery.py`
- [ ] Delete `around_the_grounds/models/schedule.py`
- [ ] Update `around_the_grounds/models/__init__.py` to final state (only new models)
- [ ] Run `grep -r "FoodTruckEvent\|from.*brewery\|import.*Brewery" around_the_grounds/` — verify zero matches

### Acceptance
- `uv run python -m pytest` — all tests pass with old model files gone
- grep audit returns zero matches
