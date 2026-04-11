# Spec 005 — Adapter Interface Update

## Problem

After spec 004, the core models are generic (`Venue`, `Event`). But the adapter layer
still uses `Brewery` and `FoodTruckEvent` internally. The bridge shim in `BaseParser`
(introduced in spec 004 step 3) needs to be removed and each parser updated to work
natively with the new types.

The goal is minimal: keep the static `ParserRegistry`, keep `BaseParser`, keep all
seven existing parsers — just update their type signatures and field references to use
`Venue` and `Event`. No structural changes to how parsers are registered or called.

---

## User Stories

### US-1 — Parsers work with generic types (P1)
As a developer, when I add a new parser for any venue type (brewery, music venue,
farmers market), I should extend `BaseParser`, accept a `Venue`, and return
`List[Event]` — with no domain-specific base class to work around.

**Acceptance criteria:**
- `BaseParser.__init__` accepts `Venue`, not `Brewery`
- `BaseParser.parse()` returns `List[Event]`, not `List[FoodTruckEvent]`
- `BaseParser.validate_event()` validates an `Event`, not `FoodTruckEvent`
- All seven existing parsers updated to match
- The bridge shim (`self.brewery = venue`) introduced in spec 004 is removed

### US-2 — Registry unchanged (P1)
As a developer, the way parsers are registered and retrieved must not change.

**Acceptance criteria:**
- `ParserRegistry` remains a static class with a dict of key → parser class
- `ParserRegistry.get_parser(key)` signature is unchanged
- All seven parsers remain registered under their existing keys
- No self-registration or dynamic import mechanism introduced

---

## Functional Requirements

1. **`BaseParser` type signatures updated** — `Venue` in, `List[Event]` out
2. **`validate_event()` updated** — checks `Event` fields (`title`, `datetime_start`,
   `venue_key`) instead of `FoodTruckEvent` fields (`food_truck_name`, `date`,
   `brewery_key`)
3. **All seven parsers updated** — each constructs `Event` objects directly instead of
   `FoodTruckEvent`; field mapping:
   - `brewery_key` / `brewery_name` → `venue_key` / `venue_name` (from `self.venue`)
   - `food_truck_name` → `title`
   - `date` + `start_time` / `end_time` → `datetime_start` / `datetime_end`
     (timezone-aware, using venue timezone)
   - `ai_generated_name=True` → `extraction_method="ai-vision"`
4. **No `FoodTruckEvent` imports remain** in any parser file after this spec
5. **Normalizer shim removed** — the bridge conversion in `BaseParser` from spec 004
   step 3 is deleted; parsers produce `Event` natively

---

## Out of Scope

- Renaming `parsers/` to `adapters/` — the directory name is fine as-is
- Changing the static registry to a dynamic/self-registering pattern
- Adding new parsers or venue types
- Changing the config file or CLI
