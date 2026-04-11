# Feature Specification: Add New Venues to a Site

**Feature Branch**: `008-add-venues-to-site`
**Created**: 2026-02-28
**Status**: Draft
**Input**: User description: "Add new venue URLs to an existing site config. The system should support venues across different web platforms using generic parsers, with AI vision/OCR as fallback, and venue-specific parsers as last resort."

## User Scenarios & Testing

### User Story 1 - Add a venue with an existing generic parser (Priority: P1)

A site operator adds a new venue URL to an existing site config JSON. The venue uses a platform already supported by a generic parser (html, ajax, wordpress). Events are scraped correctly with no code changes.

**Why this priority**: This is the most common path — most venues will fit an existing parser. Zero-code extensibility is the core value of the platform.

**Independent Test**: Add Young Ethel's (`https://youngethels.com/events`, source_type: `html`) and Roulette (`https://roulette.org/calendar/`, source_type: `html`) to park-slope-music.json, run `--preview`, verify events appear.

**Acceptance Scenarios**:

1. **Given** a new venue entry in a site config with `source_type: "html"` and appropriate CSS selectors in `parser_config`, **When** the site is scraped, **Then** events from the new venue appear alongside existing venues.
2. **Given** a new venue entry with `source_type: "ajax"` and an `api_url` + `field_map`, **When** the site is scraped, **Then** events are extracted from the JSON API response.

---

### User Story 2 - Add a venue that uses JSON-LD structured data (Priority: P1)

A site operator adds a venue whose website embeds Schema.org event data in `<script type="application/ld+json">` tags (e.g., Eastville Comedy Club). A new generic `json-ld` parser extracts events from the structured data.

**Why this priority**: JSON-LD is one of the most widely adopted structured data formats on the web. Supporting it as a generic parser unlocks a large number of future venues with zero code.

**Independent Test**: Add Eastville Comedy Club (`https://www.eastvillecomedy.com/calendar`, source_type: `json-ld`) to park-slope-music.json, run `--preview`, verify comedy events appear with correct titles and times.

**Acceptance Scenarios**:

1. **Given** a venue config with `source_type: "json-ld"`, **When** the parser fetches the page, **Then** it extracts events from all `<script type="application/ld+json">` tags containing Schema.org Event types (`Event`, `ComedyEvent`, `MusicEvent`, etc.).
2. **Given** a JSON-LD block with `startDate` in ISO 8601 format with timezone, **When** the parser processes it, **Then** both date and start_time are set correctly.
3. **Given** a page with multiple JSON-LD blocks (Organization, BreadcrumbList, Events), **When** the parser runs, **Then** only Event-type objects are extracted.
4. **Given** a JSON-LD event with `performer` and `offers.price` data, **When** processed, **Then** performer names and price are included in the event description.

---

### User Story 3 - Add a venue using WordPress Tribe Events Calendar (Priority: P1)

A site operator adds a venue powered by The Events Calendar WordPress plugin (e.g., Industry City). The existing `wordpress` parser is extended to handle Tribe Events API responses via `field_map` and `response_path` config.

**Why this priority**: The Events Calendar is the most popular WordPress events plugin. Supporting it via config extends the wordpress parser's reach significantly without a new parser class.

**Independent Test**: Add Industry City (`https://industrycity.com/events/`, source_type: `wordpress` with Tribe Events config) to park-slope-music.json, run `--preview`, verify events with correct start/end times.

**Acceptance Scenarios**:

1. **Given** a venue config with `source_type: "wordpress"`, `api_path: "/wp-json/tribe/events/v1/events"`, `response_path: "events"`, and a `field_map`, **When** scraped, **Then** events are returned with fields mapped correctly (title from `title`, date from `start_date`, etc.).
2. **Given** a Tribe Events API where `title` is a plain string (not `{ "rendered": "..." }`), **When** the parser maps it, **Then** both plain strings and WP rendered objects are handled transparently.
3. **Given** the existing childrens-events site with vanilla WordPress venues, **When** all tests run after the upgrade, **Then** they pass without modification (full backward compatibility).

---

### User Story 4 - Validate a venue URL before adding to config (Priority: P2)

A site operator can test a new venue URL against available parsers to see if it returns events before committing it to a site config.

**Why this priority**: Reduces trial-and-error when onboarding new venues. Nice-to-have but not blocking for the initial four venues.

**Independent Test**: Run a validation command against a known-good URL, verify it reports which parser matched and how many events were found.

**Acceptance Scenarios**:

1. **Given** a venue URL and source_type, **When** the operator runs a validation/test command, **Then** the system reports: parser used, number of events found, sample event titles and dates.
2. **Given** a venue URL where no parser can extract events, **When** validated, **Then** the system reports failure with suggested next steps (try different source_type, check selectors).

---

### Edge Cases

- What happens when a venue URL is unreachable? Existing error isolation handles it — other venues continue, error is reported.
- What happens when JSON-LD contains malformed JSON? Parser catches `json.JSONDecodeError`, logs warning, returns empty list.
- What happens when `field_map` references a key that doesn't exist in the API response? Field returns None; event is skipped if title or date is missing.
- What happens when `response_path` points to a non-array in WordPress response? Parser logs warning and returns empty list.
- What happens when a venue has pagination (e.g., Roulette with page/2/)? HTML parser processes first page only; pagination support is a future enhancement.

## Requirements

### Functional Requirements

- **FR-001**: System MUST support adding new venues to an existing site config JSON with no code changes when the venue matches a supported `source_type`.
- **FR-002**: System MUST register a new `JsonLdParser` generic parser for `source_type: "json-ld"` that extracts events from `<script type="application/ld+json">` tags.
- **FR-003**: `JsonLdParser` MUST filter JSON-LD objects to Schema.org Event types and subtypes (Event, ComedyEvent, MusicEvent, DanceEvent, TheaterEvent, etc.).
- **FR-004**: `JsonLdParser` MUST use Schema.org defaults for field mapping (`name` → title, `startDate` → date/start_time, `endDate` → end_time, `description` → description) with optional `field_map` override.
- **FR-005**: `JsonLdParser` MUST set `extraction_method` to `"json-ld"` on all events.
- **FR-006**: `WordPressParser` MUST be extended with optional `response_path` config to traverse into wrapped API responses (e.g., Tribe Events `{ "events": [...] }`).
- **FR-007**: `WordPressParser` MUST be extended with optional `field_map` config to map Event fields to arbitrary API response keys.
- **FR-008**: `WordPressParser` MUST maintain full backward compatibility — existing configs with no `field_map` or `response_path` work identically.
- **FR-009**: `WordPressParser` MUST handle title values as both plain strings and `{ "rendered": "..." }` objects.
- **FR-010**: `WordPressParser` MUST parse datetime strings in both ISO 8601 and WordPress local formats (`YYYY-MM-DD HH:MM:SS`).
- **FR-011**: Four new venue configs MUST be added to `park-slope-music.json`: Young Ethel's, Eastville Comedy Club, Industry City, Roulette.

### Key Entities

- **`JsonLdParser`**: New class in `parsers/generic/json_ld.py`, extends `BaseParser`.
- **`ParserRegistry._generic`**: Updated with `"json-ld": JsonLdParser`.
- **`WordPressParser`**: Extended with `response_path` and `field_map` support.
- **`Venue.parser_config`**: No model changes — already `Dict[str, Any]`.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All four venues (Young Ethel's, Eastville, Industry City, Roulette) return events via `--preview` on the park-slope-music site.
- **SC-002**: All existing tests pass without modification.
- **SC-003**: New unit tests cover: JsonLdParser extraction, type filtering, field mapping, malformed JSON; WordPressParser response_path, field_map, mixed title formats, datetime formats.
- **SC-004**: New parser tests use captured HTML/JSON fixtures from real venue responses.
- **SC-005**: Zero venue-specific parser code — all four venues use generic parsers via config only.
