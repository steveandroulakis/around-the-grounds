---
id: WP05
title: Remove deprecated models
lane: planned
depends_on: [WP04]
feature: 004-generic-models
---

# WP05 — Remove deprecated models

## Goal
Delete `brewery.py` and `schedule.py`, update `__init__.py` to export only the new models, and verify via grep that no production code references the old types.

## Context
- Upstream-first: this WP is a clean PR to around-the-grounds main
- Minimalism: change only what is listed, nothing else
- Branch: `004-generic-models`

## Subtasks
- [ ] Delete `around_the_grounds/models/brewery.py`
- [ ] Delete `around_the_grounds/models/schedule.py`
- [ ] Update `around_the_grounds/models/__init__.py` to final state (only new models)
- [ ] Run `grep -r "FoodTruckEvent\|from.*brewery\|import.*Brewery" around_the_grounds/` — verify zero matches

## Files to change
- `around_the_grounds/models/brewery.py` — DELETE
- `around_the_grounds/models/schedule.py` — DELETE
- `around_the_grounds/models/__init__.py` — final state:
  ```python
  from .event import Event, Location
  from .venue import Venue
  from .venue_list import VenueList

  __all__ = ["Event", "Location", "Venue", "VenueList"]
  ```

## Acceptance criteria
- `uv run python -m pytest` — all 196 tests pass with old model files gone
- `grep -r "FoodTruckEvent\|from.*brewery\|import.*Brewery" around_the_grounds/` returns zero matches

## Notes
- This WP is only safe after WP04 has made the full test suite green — do not merge until WP04 is complete and all tests pass.
- The `utc_to_pacific_naive()` function in `timezone_utils.py` is not deleted here; it was kept through WP02 to avoid touching more files than necessary. If desired, it can be removed in a follow-up cleanup, but it is not required for this spec.
- `VenueList` is exported but not used in production yet — that is intentional, deferred to spec 006.
