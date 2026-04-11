---
id: WP01
title: Copy ventr models into ATG
lane: planned
depends_on: []
feature: 004-generic-models
---

# WP01 — Copy ventr models into ATG

## Goal
Add `Event`, `Location`, `Venue`, and `VenueList` model files to `around_the_grounds/models/` so that old and new models are importable simultaneously, with zero changes to any other code.

## Context
- Upstream-first: this WP is a clean PR to around-the-grounds main
- Minimalism: change only what is listed, nothing else
- Branch: `004-generic-models`

## Subtasks
- [ ] Create `around_the_grounds/models/event.py` (copy from ventr, fix import path)
- [ ] Create `around_the_grounds/models/venue.py` (copy from ventr, fix import path)
- [ ] Create `around_the_grounds/models/venue_list.py` (copy from ventr, fix import path)
- [ ] Update `around_the_grounds/models/__init__.py` to export new models alongside old

## Files to change
- `around_the_grounds/models/event.py` — CREATE. Copy `Location` and `Event` verbatim from `ventr/ventr/models/event.py`. No import path changes needed.
- `around_the_grounds/models/venue.py` — CREATE. Copy `Venue` verbatim from `ventr/ventr/models/venue.py`. Change import: `from ventr.models.event import Location` → `from .event import Location`
- `around_the_grounds/models/venue_list.py` — CREATE. Copy `VenueList` verbatim from `ventr/ventr/models/venue_list.py`. Change import: `from ventr.models.venue import Venue` → `from .venue import Venue`
- `around_the_grounds/models/__init__.py` — UPDATE exports to:
  ```python
  from .brewery import Brewery
  from .schedule import FoodTruckEvent
  from .event import Event, Location
  from .venue import Venue
  from .venue_list import VenueList

  __all__ = ["Brewery", "FoodTruckEvent", "Event", "Location", "Venue", "VenueList"]
  ```

## Acceptance criteria
- `python -c "from around_the_grounds.models import Venue, Event, Location, VenueList"` succeeds
- Old models still importable (no breakage): `python -c "from around_the_grounds.models import Brewery, FoodTruckEvent"` succeeds

## Notes
- `VenueList` will be importable but not used in production code until spec 006; that is intentional.
- `Event.__post_init__` raises `ValueError` if `datetime_start.tzinfo is None` — existing code using `FoodTruckEvent` is not affected until WP02.
- Source files are in the `ventr` sibling repo at `/Users/jacob.redding/code/ventr/kitty-specs` — check `ventr/ventr/models/` for the canonical source.
