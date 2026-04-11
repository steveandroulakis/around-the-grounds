# Implementation Plan: 005 — Adapter Interface Update

**Branch**: `005-adapter-interface-update` | **Date**: 2026-02-25 | **Spec**: [spec.md](spec.md)

## Summary

Remove all `Brewery`/`FoodTruckEvent` references from the parser layer. Each of the 7 parsers
and `BaseParser` accept `Venue` and return `List[Event]` natively. No shim, no compatibility
alias, no structural changes. The static registry, `parsers/` directory name, and all parser
logic are untouched.

## Technical Context

- **Language/Version**: Python 3.8+
- **Primary Dependencies**: aiohttp, beautifulsoup4, anthropic (UrbanFamily only)
- **Testing**: pytest, 196 tests — all must pass
- **Constraints**: Zero test deletions; no parser logic, registry, or directory changes

## Boundary Analysis — Spec 004 WP02 vs. Spec 005

Spec 004's WP02 specifies the same transformations as spec 005. Spec 005 is the
formal standalone deliverable for those changes with 4 items that deserve explicit
callout beyond the WP02 sweep:

1. **`UrbanFamilyParser.__init__` and `SalehsCornerParser.__init__`** — both have
   explicit `(self, brewery: Brewery)` overrides at the parser level (not inherited).
   Easy to miss in a general `self.brewery` sweep.

2. **`WheeliePopParser._event_key()`** — accesses `event.date` and `event.food_truck_name`.
   Both fields no longer exist on `Event`. This is a silent runtime breakage with no
   test guard if missed.

3. **FR4 audit gate** — grep confirmation that zero `FoodTruckEvent` imports remain in
   `parsers/`. Required before merge, not just assumed.

4. **`SalehsCorner` extraction method** — vendor names come from the
   seattlefoodtruck.com API, not HTML parsing. Should be `extraction_method="api"`,
   not `"html"`. The general WP02 mapping defaults to `"html"` for `ai_generated_name=False`
   but spec 005 FR3 makes `"api"` explicit for this parser.

## Project Structure

Only these 8 files change:

```
around_the_grounds/parsers/
├── base.py              (type signatures only — 10 atomic edits)
├── stoup_ballard.py     (self.venue + Event + tz-aware)
├── bale_breaker.py      (self.venue + Event + remove tzinfo strip)
├── urban_family.py      (explicit __init__ + self.venue + Event + remove tzinfo strip)
├── obec_brewing.py      (self.venue + Event + now_in_pacific)
├── chucks_greenwood.py  (self.venue + Event + PACIFIC_TZ attach)
├── salehs_corner.py     (explicit __init__ + self.venue + Event + utc_to_pacific_aware + "api")
└── wheelie_pop.py       (self.venue + Event + utc_to_pacific_aware + _event_key fix)
```

`parsers/registry.py` — **untouched**. Diff must be empty.

## Work Packages

### WP01 — Update `BaseParser` type signatures

**File**: `around_the_grounds/parsers/base.py`

10 atomic edits, in order:

1. Import L8: `from ..models import Brewery, FoodTruckEvent` → `from ..models import Venue, Event`
2. `__init__` sig: `def __init__(self, brewery: Brewery):` → `def __init__(self, venue: Venue):`
3. `__init__` body: `self.brewery = brewery` → `self.venue = venue`
4. `parse()` return: `List[FoodTruckEvent]` → `List[Event]`
5. `validate_event()` sig: `event: FoodTruckEvent` → `event: Event`
6. `validate_event()` body: `event.brewery_key` → `event.venue_key`
7. `validate_event()` body: `event.brewery_name` → `event.venue_name`
8. `validate_event()` body: `event.food_truck_name` → `event.title`
9. `validate_event()` body: `event.date` → `event.datetime_start`
10. `filter_valid_events()` sig: `List[FoodTruckEvent]` → `List[Event]` (both param and return)

No logic change. No method rename.

**Depends on**: Spec 004 WP01 (models importable)
**Testable**: `python -c "from around_the_grounds.parsers.base import BaseParser"` — no import error

---

### WP02 — Update all 7 parsers

**Goal**: Each parser constructs `Event` objects directly with tz-aware `datetime_start`.

#### Per-parser change inventory

**`stoup_ballard.py`**
- Import: `FoodTruckEvent` → `Event`; add `PACIFIC_TZ` from `timezone_utils`
- `self.brewery.*` → `self.venue.*`: 7 occurrences
- 3 `FoodTruckEvent(...)` → `Event(...)` construction sites
- Timezone: `date=current_date` → `datetime_start=current_date.replace(tzinfo=PACIFIC_TZ)`
- `start_time` / `end_time` → `.replace(tzinfo=PACIFIC_TZ)` if not None
- `ai_generated_name=False` → `extraction_method="html"`

**`bale_breaker.py`**
- Import: `FoodTruckEvent` → `Event`
- `self.brewery.*` → `self.venue.*`: 6 occurrences
- 2 `FoodTruckEvent(...)` → `Event(...)` construction sites
- Timezone: remove `.replace(tzinfo=None)` at the two `pacific_tz` conversion sites —
  the `astimezone(pacific_tz)` result is already tz-aware; just stop stripping it
- Fallback event: `date=datetime.now()` → `datetime_start=datetime.now(ZoneInfo("America/Los_Angeles"))`
- `ai_generated_name=False` → `extraction_method="html"`

**`urban_family.py`**
- Import: `from ..models import Brewery, FoodTruckEvent` → `from ..models import Venue, Event`
- **`__init__` override** (explicit, not inherited):
  `def __init__(self, brewery: Brewery) -> None:` → `def __init__(self, venue: Venue) -> None:`
  `super().__init__(brewery)` → `super().__init__(venue)`
- `self.brewery.*` → `self.venue.*`: 7 occurrences
- 1 `FoodTruckEvent(...)` → `Event(...)` construction site
- Timezone: remove `.replace(tzinfo=None)` from `_parse_time_string()` ISO conversion;
  for 24-hour and 12-hour formats, use `.replace(..., tzinfo=PACIFIC_TZ)` instead of naive
- `ai_generated=True` → `extraction_method="ai-vision"`; `False` → `extraction_method="html"`
- `_extract_food_truck_name()` return `(name, bool)` tuple is unchanged internally;
  the bool is consumed at the callsite in `_parse_event_item()` to set `extraction_method`

**`obec_brewing.py`**
- Import: `FoodTruckEvent` → `Event`;
  `now_in_pacific_naive` → `now_in_pacific` (tz-aware variant already exists)
- `self.brewery.*` → `self.venue.*`: 3 occurrences
- 1 `FoodTruckEvent(...)` → `Event(...)` construction site
- Timezone: `now_in_pacific_naive()` → `now_in_pacific()` throughout; result is already
  tz-aware — no `.replace(tzinfo=...)` needed
- `ai_generated_name=False` → `extraction_method="html"`

**`chucks_greenwood.py`**
- Import: `FoodTruckEvent` → `Event`; add `PACIFIC_TZ` from `timezone_utils`
- `self.brewery.*` → `self.venue.*`: 3 occurrences
- 1 `FoodTruckEvent(...)` → `Event(...)` construction site
- Timezone: `parse_date_with_pacific_context(...)` returns naive →
  add `.replace(tzinfo=PACIFIC_TZ)` to the result
- `ai_generated_name=False` → `extraction_method="html"`

**`salehs_corner.py`**
- Import: `from ..models import Brewery, FoodTruckEvent` → `from ..models import Venue, Event`
- Import: `utc_to_pacific_naive` → `utc_to_pacific_aware` (new helper from spec 004 WP02)
- **`__init__` override** (explicit, not inherited):
  `def __init__(self, brewery: Brewery) -> None:` → `def __init__(self, venue: Venue) -> None:`
  `super().__init__(brewery)` → `super().__init__(venue)`
- `self.brewery.*` → `self.venue.*`: 4 occurrences
- 1 `FoodTruckEvent(...)` → `Event(...)` construction site
- Timezone: `_parse_iso_timestamp()` — `utc_to_pacific_naive(...)` → `utc_to_pacific_aware(...)`
- `_parse_event_timestamps()` — `now_in_pacific_naive()` → `now_in_pacific()` (tz-homogeneous comparison)
- `_get_api_date_range()` — `now_in_pacific_naive()` used only for date arithmetic, no change needed
- `ai_generated_name=False` → `extraction_method="api"` ← vendor names come from API, not HTML

**`wheelie_pop.py`**
- Import: `FoodTruckEvent` → `Event`; `utc_to_pacific_naive` → `utc_to_pacific_aware`
- `self.brewery.*` → `self.venue.*`: 3 occurrences
- 1 `FoodTruckEvent(...)` → `Event(...)` construction site
- Timezone: `_parse_time()` — `utc_to_pacific_naive(parsed)` → `utc_to_pacific_aware(parsed)`
- **`_event_key()` fix** (silent runtime breakage if missed):
  - `event.date.strftime('%Y-%m-%d')` → `event.datetime_start.strftime('%Y-%m-%d')`
  - `event.food_truck_name.lower()` → `event.title.lower()`
  - `event.start_time` → `event.datetime_start` (for the formatted time component)
- Type annotations L25, L113, L126: `List[FoodTruckEvent]` → `List[Event]`
- `ai_generated_name=False` → `extraction_method="html"`

**Depends on**: WP01
**Testable**: All 196 tests pass (with test fixture updates from Spec 004 WP04 applied)

---

### WP03 — FR4 audit (zero legacy references in parsers)

Verification step — not a separate commit.

```bash
grep -r "FoodTruckEvent" around_the_grounds/parsers/   # must return zero matches
grep -r "from.*Brewery\|import.*Brewery" around_the_grounds/parsers/  # must return zero matches
```

This is the exit criterion for WP02, not a separate deliverable. Run before opening PR.

---

## Dependency Order

```
Spec 004 WP01 (Venue, Event importable)
  └─→ WP01 (BaseParser signatures)
        └─→ WP02 (all 7 parsers — can be committed per-file)
              └─→ WP03 (grep audit — exit criterion)
```

Parsers may be updated and committed individually within WP02. All 7 must pass the
WP03 audit before the branch is merged.

---

## Minimalism Confirmation

Changes are limited to 8 files. No changes to:
- `parsers/registry.py` — registry lookup is key → class; class signatures change but
  the registry is unaffected. **Diff must be empty.**
- `parsers/__init__.py` — unchanged
- `scrapers/coordinator.py` — covered by Spec 004 WP02
- `main.py`, `haiku_generator.py`, `activities.py` — covered by Spec 004 WP03
- All test files — covered by Spec 004 WP04
- `models/brewery.py`, `models/schedule.py` — deletion deferred to Spec 004 WP05

---

## Upstream PR Notes

**PR title**: `parsers: migrate from Brewery/FoodTruckEvent to Venue/Event`

**Reviewer checklist**:

1. `grep -r "FoodTruckEvent\|import.*Brewery" around_the_grounds/parsers/` returns zero — if not, a parser was missed
2. Every `datetime_start=` argument is tz-aware (has `tzinfo`). `Event.__post_init__` catches this at runtime but tests should too
3. `UrbanFamilyParser.__init__` and `SalehsCornerParser.__init__` both updated — not just `BaseParser.__init__`
4. `WheeliePopParser._event_key()` updated — silent deduplication breakage if missed
5. `salehs_corner.py` uses `extraction_method="api"` — not `"html"`
6. `parsers/registry.py` diff is empty
