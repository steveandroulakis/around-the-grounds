# Spec 006 — Multi-Config Deployment

## Problem

Around-the-grounds today has a single hardcoded deployment target (`breweries.json` +
`DEFAULT_GIT_REPOSITORY` in `settings.py`). Adding a second site — say, a music venue
aggregator or a farmers market calendar — would require forking the codebase or
adding messy environment variable overrides.

The fix is to make the JSON config file the single source of truth for one deployment.
Each JSON file fully describes one website: what to scrape, where to deploy it, and
what it looks like. The CLI accepts the file path as an argument — no hardcoded
defaults, no env var fallbacks needed for the common case.

---

## User Stories

### US-1 — One config file, one website (P1)
As an operator, I should be able to run two independent deployments from the same
codebase by pointing the CLI at two different JSON files.

```bash
uv run around-the-grounds food-trucks.json --deploy
uv run around-the-grounds music-venues.json --deploy
```

Each command produces a separate website at a separate URL with its own event data.

**Acceptance criteria:**
- CLI accepts a required positional argument: path to a JSON config file
- The config file contains all information needed for one complete deployment
- Two different config files produce two independent websites
- No deployment information is hardcoded in the codebase

### US-2 — Config file is self-documenting (P1)
As a new developer, when I open a config file I should immediately understand
what site it produces, what it aggregates, and where it deploys.

**Acceptance criteria:**
- Config file contains `list_name` (human-readable name for the site)
- Config file contains `target_url` (the live public URL, informational)
- Config file contains `target_repo` and `target_branch` (deployment destination)
- Config file contains `template_dir` (optional path to HTML template)
- Config file contains `venues` (list of sources to aggregate)

### US-3 — Invalid config fails fast (P1)
As an operator, if I pass a malformed config file the CLI should report the
problem clearly before attempting any network requests.

**Acceptance criteria:**
- Config is validated against a JSON Schema at startup
- Validation errors report the specific field and problem
- A missing required field (e.g. `target_repo`) fails with a clear message

---

## Config File Schema

Each config file is a `VenueList` document:

```json
{
  "list_name": "Brooklyn Food Trucks",
  "target_url": "https://brooklyn-food-trucks.vercel.app",
  "target_repo": "https://github.com/user/brooklyn-food-trucks-site",
  "target_branch": "main",
  "template_dir": "public_template",
  "venues": [
    {
      "key": "stoup-ballard",
      "name": "Stoup Brewing Ballard",
      "url": "https://stoupbrewing.com/ballard/",
      "source_type": "html",
      "timezone": "America/Los_Angeles"
    }
  ]
}
```

**Required fields:** `list_name`, `target_repo`, `venues`
**Optional fields:** `target_url`, `target_branch` (default: `"main"`), `template_dir`

### Field Notes

- **`target_url`** — informational only; the live public URL of the deployed site.
  Not used by the deployment process itself. Documents where the output will be visible.
- **`target_repo`** — the git repository to push the generated static site to.
  Must be a valid HTTPS git URL.
- **`template_dir`** — path to the HTML/CSS/JS template directory, relative to the
  config file's location. Defaults to the built-in `public_template/` if omitted.

> **Future:** A richer `deployment` block may be added to support different hosting
> providers (Vercel, Netlify, S3), authentication methods, and CDN configuration.
> This is deferred until multiple deployment targets are needed in practice.

---

## CLI Changes

The CLI `around-the-grounds` command is updated to accept the config file as a
required positional argument:

```bash
# Before (hardcoded default, env var override)
uv run around-the-grounds --deploy
uv run around-the-grounds --config /path/to/breweries.json --deploy

# After (explicit, required)
uv run around-the-grounds food-trucks.json --deploy
uv run around-the-grounds music-venues.json --deploy --verbose
uv run around-the-grounds food-trucks.json --preview
```

The `--config` / `-c` flag is replaced by a required positional argument.
The `--git-repo` flag and `GIT_REPOSITORY_URL` env var are removed — the config
file owns the deployment target.

---

## Functional Requirements

1. **CLI positional argument** — `venues_config` is a required positional argument;
   the CLI exits with a clear usage error if omitted
2. **Config validation** — JSON Schema validation runs before any scraping; failures
   report field name and message
3. **`target_repo` from config** — deployment uses `config.target_repo` + `config.target_branch`;
   the `--git-repo` flag and `GIT_REPOSITORY_URL` env var are removed
4. **`template_dir` from config** — if set, resolved relative to the config file's
   parent directory; if omitted, built-in `public_template/` is used
5. **Existing `breweries.json` migrated** — the existing config is updated to the
   new schema (add `list_name`, `target_repo`, `source_type` per venue, etc.)
6. **CLAUDE.md updated** — development commands updated to reflect new CLI syntax

---

## Out of Scope

- Supporting multiple config files in a single CLI invocation
- Richer deployment metadata (provider-specific config, auth method selection)
- Temporal workflow updates (the workflow receives `venues_config_path` already)
- Adding new venue types
