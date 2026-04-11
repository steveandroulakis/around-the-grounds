# Feature Specification: Recursive Event Gathering

**Feature Branch**: `010-recursive-event-gathering`
**Created**: 2026-03-01
**Status**: Draft
**Input**: User description: "When a venue's calendar page links to external event pages (e.g., Eventbrite), follow those links to extract richer event data such as start/end times from structured data (JSON-LD). This enables time extraction from JS-rendered venues like Union Hall that only expose times on individual event pages, not on the calendar listing."

## User Scenarios & Testing

### User Story 1 - Extract times from linked Eventbrite pages (Priority: P1)

A venue's calendar page (e.g., Union Hall) lists events with links to Eventbrite but no time information in the listing HTML. The parser follows each Eventbrite link and extracts start/end times from the event page's JSON-LD structured data.

**Why this priority**: This is the motivating use case. Union Hall's calendar has no time data in its HTML; times only exist on individual Eventbrite event pages as JSON-LD `startDate`/`endDate`.

**Independent Test**: Configure Union Hall with recursive gathering enabled, scrape the calendar, verify events have `start_time` and `end_time` populated from Eventbrite JSON-LD.

**Acceptance Scenarios**:

1. **Given** a venue config with recursive event gathering enabled and events linking to Eventbrite, **When** the parser scrapes the calendar, **Then** each event's `start_time` and `end_time` are populated from the linked page's JSON-LD.
2. **Given** an Eventbrite link that fails to load or has no JSON-LD, **When** the parser follows it, **Then** the event is kept with `start_time: None` (graceful degradation, no crash).
3. **Given** a venue with 15 Eventbrite links, **When** recursive gathering runs, **Then** all links are fetched concurrently within the existing session timeout.

---

### User Story 2 - Generic link-following for any external event page (Priority: P2)

Recursive gathering works with any external event page that has JSON-LD structured data (not just Eventbrite). The parser extracts `startDate`/`endDate` from any `Event` schema type found in JSON-LD.

**Why this priority**: Other venues may link to non-Eventbrite ticketing platforms (Dice, See Tickets, venue-hosted pages) that also use JSON-LD. Generic support avoids vendor lock-in.

**Independent Test**: Create a mock event page with JSON-LD `Event` schema, configure a venue to follow links, verify times are extracted.

**Acceptance Scenarios**:

1. **Given** a linked event page with JSON-LD `@type: "Event"` containing `startDate`, **When** the parser follows the link, **Then** `start_time` is extracted regardless of the hosting platform.
2. **Given** a linked page with multiple JSON-LD blocks, **When** the parser scans them, **Then** it finds the first `Event` type and uses its dates.

---

### User Story 3 - Config-driven opt-in per venue (Priority: P1)

Recursive gathering is enabled per-venue via `parser_config` flags. It is never on by default — venues must explicitly opt in.

**Why this priority**: Following external links adds latency and network requests. It must be opt-in to avoid scraping pages unnecessarily.

**Independent Test**: Verify that venues without the config flag do not follow any links; verify that enabling the flag causes links to be followed.

**Acceptance Scenarios**:

1. **Given** a venue config with `"follow_links_for_times": true` and a `"link_selector"` CSS selector, **When** the parser runs, **Then** it extracts URLs from matching elements and fetches them.
2. **Given** a venue config without `follow_links_for_times`, **When** the parser runs, **Then** no external links are followed (existing behavior unchanged).

---

### Edge Cases

- What happens when a linked page returns a redirect chain (e.g., Eventbrite short URLs)?
- How does the system handle rate limiting from Eventbrite or other ticketing platforms?
- What happens when the linked page's JSON-LD `startDate` disagrees with the date parsed from the calendar listing?
- What if `link_selector` matches non-event links (e.g., venue homepage, sponsor links)?
- How are duplicate events handled if the same Eventbrite link appears in multiple calendar entries?

## Requirements

### Functional Requirements

- **FR-001**: System MUST support a `follow_links_for_times: true` flag in venue `parser_config` to enable recursive gathering.
- **FR-002**: System MUST accept a `link_selector` CSS selector in `parser_config` to identify which links to follow within each event container.
- **FR-003**: System MUST extract `startDate` and `endDate` from JSON-LD `Event` schema on linked pages.
- **FR-004**: System MUST fetch linked pages concurrently using the existing `aiohttp` session.
- **FR-005**: System MUST gracefully degrade — if a linked page fails or has no JSON-LD, the event is kept without times (not dropped).
- **FR-006**: System MUST NOT follow links for venues that do not have `follow_links_for_times: true` (no behavior change for existing venues).
- **FR-007**: System MUST respect the existing session timeout for all linked-page fetches.

### Key Entities

- **Event Container**: The HTML element on the calendar page representing one event (existing).
- **Event Link**: A URL found within the event container via `link_selector` that points to an external event page.
- **JSON-LD Event Schema**: Structured data on the linked page containing `startDate`/`endDate` fields.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Union Hall events display start and end times on the park-slope-music site.
- **SC-002**: Existing venues without `follow_links_for_times` have zero behavior change (no additional HTTP requests).
- **SC-003**: All existing tests continue to pass with no modifications.
- **SC-004**: Recursive gathering adds no more than 10 seconds to a venue's total scrape time (concurrent fetches).
