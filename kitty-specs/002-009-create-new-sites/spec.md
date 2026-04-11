# Feature Specification: Create New Sites

**Feature Branch**: `009-create-new-sites`
**Created**: 2026-02-28
**Status**: Draft
**Input**: User description: "Streamline the process of creating entirely new sites with their own config, template, and deployment target. A new site should be creatable with minimal effort and no code changes."

## User Scenarios & Testing

### User Story 1 - Create a new site from an existing template (Priority: P1)

A site operator creates a new site by adding a JSON config file to `config/sites/` that references an existing template (food-trucks, music, or kids). The site is immediately runnable via `--site <key>`.

**Why this priority**: This is the current workflow but undocumented and manual. Making it explicit and validated is the foundation for everything else.

**Independent Test**: Create a new site config JSON referencing the `music` template with one venue, run `--site <key> --preview`, verify the site generates correctly.

**Acceptance Scenarios**:

1. **Given** a new JSON file in `config/sites/` with valid `key`, `name`, `template`, `timezone`, `target_repo`, and `venues`, **When** the operator runs `--site <key>`, **Then** the site scrapes and outputs events.
2. **Given** a new site config referencing `template: "music"`, **When** `--preview` is run, **Then** the music template is copied to `public/` with the site's `data.json`.
3. **Given** a new site config, **When** `--site all` is run, **Then** the new site is included in the batch alongside existing sites.

---

### User Story 2 - Create a new site with a custom template (Priority: P2)

A site operator creates a new visual template for a different event domain (e.g., comedy, art, markets) by adding a directory to `public_templates/` and referencing it in the site config.

**Why this priority**: Reusing existing templates covers many cases, but new event domains benefit from purpose-built UI. This is the natural next step after P1.

**Independent Test**: Create a new `comedy` template directory with an `index.html`, reference it in a site config, run `--preview`, verify the custom template is served.

**Acceptance Scenarios**:

1. **Given** a new directory `public_templates/comedy/` with an `index.html`, **When** a site config sets `template: "comedy"`, **Then** `--preview` copies that template to `public/`.
2. **Given** a site config referencing a template that doesn't exist, **When** the site runs, **Then** a clear error message identifies the missing template.

---

### User Story 3 - Scaffold a new site via CLI command (Priority: P3)

A site operator can run a CLI command to generate a skeleton site config and optionally scaffold a new template, reducing manual file creation.

**Why this priority**: Quality-of-life improvement. The manual process (copy a JSON, edit fields) works fine for occasional use. Scaffolding helps when creating many sites.

**Independent Test**: Run the scaffold command, verify it creates a valid config JSON and optional template directory.

**Acceptance Scenarios**:

1. **Given** the operator runs a scaffold command with a site key, name, and timezone, **When** it completes, **Then** a valid `config/sites/<key>.json` is created with placeholder venues.
2. **Given** the operator passes `--template new` to the scaffold, **When** it completes, **Then** a new template directory is created in `public_templates/` with a minimal `index.html` that loads `data.json`.
3. **Given** the operator passes `--template music` to the scaffold, **When** it completes, **Then** the config references the existing music template (no new directory created).

---

### User Story 4 - Validate a site config before running (Priority: P2)

The system validates site config files on load, providing clear error messages for missing or invalid fields.

**Why this priority**: As more people create sites, config validation prevents confusing runtime errors. Important for the "no code changes" promise.

**Independent Test**: Create a config with a missing required field, run the site, verify a helpful error message.

**Acceptance Scenarios**:

1. **Given** a site config missing the `key` field, **When** loaded, **Then** a clear error names the missing field and the file path.
2. **Given** a site config with a venue missing `url`, **When** loaded, **Then** a clear error identifies the venue and the missing field.
3. **Given** a site config with an unknown `source_type` on a venue, **When** scraped, **Then** the error message lists available source types.

---

### Edge Cases

- What happens when two site configs use the same `key`? Loader should detect and error on duplicate keys.
- What happens when a site config has zero venues? Site runs but produces no events — log a warning.
- What happens when `target_repo` is not set and `--deploy` is used? Error with a clear message about the missing deployment target.
- What happens when a template directory is empty (no index.html)? Error during `--preview`/`--deploy` identifying the missing file.

## Requirements

### Functional Requirements

- **FR-001**: A new site MUST be creatable by adding a single JSON file to `config/sites/` with no code changes.
- **FR-002**: The config loader MUST validate required fields (`key`, `name`, `template`, `timezone`, `venues`) on load and provide clear error messages.
- **FR-003**: The config loader MUST validate that each venue has required fields (`key`, `name`, `url`, `source_type`).
- **FR-004**: The system MUST validate that the referenced `template` directory exists in `public_templates/` before attempting to copy files.
- **FR-005**: The system SHOULD provide a CLI scaffold command (e.g., `--init-site <key>`) that generates a skeleton site config.
- **FR-006**: The scaffold SHOULD optionally create a new template directory with a minimal working `index.html`.
- **FR-007**: The system MUST report available `source_type` values when a venue references an unsupported type.
- **FR-008**: Duplicate site keys across config files MUST be detected and reported as an error.

### Key Entities

- **`SiteConfig`**: No model changes — validation added at load time in `config/loader.py`.
- **Site config JSON schema**: Documented and enforced by the loader.
- **Template directory contract**: `public_templates/<template>/index.html` must exist.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A new site can be created and serving events in under 5 minutes with no code changes (config + existing template).
- **SC-002**: All validation errors produce actionable messages that name the specific field, file, and expected value.
- **SC-003**: All existing tests pass without modification.
- **SC-004**: New tests cover: config validation (missing fields, bad types, duplicates), template resolution, scaffold output (if implemented).
- **SC-005**: Documentation in ADDING-VENUES.md is updated to cover full site creation workflow.
