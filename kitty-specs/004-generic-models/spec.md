# Spec 004 — Generic Models

## Problem

Around-the-grounds uses domain-specific models (`Brewery`, `FoodTruckEvent`) that are
tightly coupled to the food truck use case. Every field name, every validation, and every
downstream reference assumes breweries and food trucks. This makes it impossible to reuse
the same codebase for music venues, farmers markets, children's events, or any other
event type without forking the project.

The fix is a full model substitution: replace domain-specific types with ventr's generic
`Venue`, `Event`, `Location`, and `VenueList`. Domain specificity moves into the adapters
— the core knows nothing about food trucks.

---

## User Stories

### US-1 — Any venue type, same codebase (P1)
As a developer adding a new event source (music venue, farmers market, kids event),
I should be able to define it as a `Venue` and have its events flow through the existing
coordinator, output, and deployment pipeline without any changes to core code.

**Acceptance criteria:**
- `Venue` replaces `Brewery` everywhere in the codebase
- `Event` replaces `FoodTruckEvent` everywhere in the codebase
- No field in `Venue` or `Event` is specific to food trucks or breweries
- Existing brewery parsers continue to work after the substitution

### US-2 — Event times are unambiguous (P1)
As a user viewing events from venues in different cities or timezones,
I should always see the correct local time for each event.

**Acceptance criteria:**
- `Event.datetime_start` and `Event.datetime_end` are always timezone-aware datetimes
- A naive datetime passed to `Event` raises a `ValueError` at construction time
- The existing Pacific-timezone handling in parsers is preserved but expressed as
  a `ZoneInfo("America/Los_Angeles")` assignment, not a hardcoded string

### US-3 — Event location is structured (P2)
As a developer building a map or filter view,
I should be able to access an event's address and coordinates as structured data.

**Acceptance criteria:**
- `Location` dataclass is available with `address`, `lat`, `lng`, `timezone` fields
- `Venue.location` accepts an optional `Location`
- `Event.location` accepts an optional `Location` (inheritable from venue)

---

## Functional Requirements

1. **Model substitution is complete** — no remaining references to `Brewery` or
   `FoodTruckEvent` outside of the adapter layer (parsers may still use these internally
   as an intermediate representation during the transition, but must not expose them
   upstream)
2. **`Venue` includes `source_type`** — valid values: `"html"`, `"ical"`, `"api"`;
   validated at construction time
3. **`Event.extraction_method`** replaces the `ai_generated_name: bool` flag —
   valid values: `"html"`, `"ical"`, `"api"`, `"ai-vision"`
4. **`VenueList` is a first-class model** — represents a named collection of venues
   with a deployment target; the config loader returns a `VenueList`
5. **Existing tests updated** — all references to `Brewery`/`FoodTruckEvent` in tests
   are updated to use the new models; no tests deleted

---

## Out of Scope

- Changing the adapter/parser structure (spec 005)
- Changing the config file format or CLI (spec 006)
- Adding new venue types or adapters
- Migrating the Temporal workflow
