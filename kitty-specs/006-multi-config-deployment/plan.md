# Implementation Plan: 006 — Multi-Config Deployment

**Branch**: `006-multi-config-deployment` | **Date**: 2026-02-25 | **Spec**: [spec.md](spec.md)

## Summary

Make each JSON config file a self-contained deployment unit. One file = one website. The CLI
accepts the config file as a required positional argument. Deployment target (`target_repo`,
`target_branch`) and template are read from the config file — no more hardcoded defaults or
`--git-repo` flag.

## Technical Context

- **Language/Version**: Python 3.8+
- **Primary Dependencies**: argparse (existing), jsonschema (new)
- **Testing**: pytest, 196 tests — all must pass; new loader tests added
- **Constraints**: `Brewery` model unchanged; parser/scraper logic unchanged; core deploy git logic unchanged

## Current State

### `breweries.json` today
```json
{
  "breweries": [
    { "key": "stoup-ballard", "name": "...", "url": "...", "parser_config": { ... } }
  ]
}
```
Top-level key `"breweries"`. No deployment fields. No `source_type` per venue.

### Deployment target today
Resolved via `config/settings.py`:
```python
DEFAULT_GIT_REPOSITORY = "https://github.com/steveandroulakis/ballard-food-trucks.git"
def get_git_repository_url(override_url: Optional[str] = None) -> str:
    return override_url or os.getenv("GIT_REPOSITORY_URL") or DEFAULT_GIT_REPOSITORY
```
Chain: CLI `--git-repo` → `GIT_REPOSITORY_URL` env var → hardcoded constant.

### Template dir today
Hardcoded as `Path.cwd() / "public_template"` in:
- `main.py` `_deploy_with_github_auth()` (line ~286)
- `main.py` `preview_locally()` (line ~369)
- `temporal/activities.py` `deploy_to_git()` (line ~222)

### Branch today
Hardcoded as `"main"` in `git push origin main`:
- `main.py` (line ~338)
- `temporal/activities.py` (line ~280)

### CLI today
```
around-the-grounds [--config PATH] [--deploy] [--git-repo URL] [--preview] [--verbose]
```

### Temporal `WorkflowParams` today
```python
@dataclass
class WorkflowParams:
    config_path: Optional[str] = None
    deploy: bool = False
    git_repository_url: str = DEFAULT_GIT_REPOSITORY
    max_parallel_scrapes: int = 10
```

---

## Target State

### New config file shape
```json
{
  "list_name": "Ballard Food Trucks",
  "target_repo": "https://github.com/steveandroulakis/ballard-food-trucks.git",
  "target_branch": "main",
  "target_url": "https://ballard-food-trucks.vercel.app",
  "venues": [
    {
      "key": "stoup-ballard",
      "name": "Stoup Brewing - Ballard",
      "url": "https://www.stoupbrewing.com/ballard/",
      "source_type": "html",
      "timezone": "America/Los_Angeles",
      "parser_config": { ... }
    }
  ]
}
```

### New CLI
```
around-the-grounds <venues_config> [--deploy] [--preview] [--verbose]
```
`venues_config` — required positional. `--config` and `--git-repo` removed.

### New `WorkflowParams`
```python
@dataclass
class WorkflowParams:
    config_path: str = ""
    deploy: bool = False
    max_parallel_scrapes: int = 10
    # git_repository_url removed — sourced from config file
```

---

## Work Packages

### WP01 — JSON Schema + config loader

**New: `around_the_grounds/config/schemas/food-trucks-config.schema.json`**

Adapted from ventr's schema. Required at top level: `list_name`, `target_repo`, `venues`.
Per venue required: `key`, `name`, `url`, `source_type` (enum: `html|ical|api`).
Optional top-level: `target_branch` (default `"main"`), `target_url`, `template_dir`.
Optional per venue: `timezone`, `parser_config`.
Do NOT include `location` — not used by food truck parsers.

**New: `around_the_grounds/config/loader.py`**

```python
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

import jsonschema

from ..models import Brewery

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "food-trucks-config.schema.json"


@dataclass
class VenueList:
    list_name: str
    venues: List[Brewery]
    target_repo: str
    target_branch: str = "main"
    target_url: Optional[str] = None
    template_dir: Optional[str] = None


class ConfigValidationError(Exception):
    """Raised when a config file fails schema validation."""
    pass


def load_venue_list(config_path: Union[str, Path]) -> VenueList:
    """Load and validate a venues config file, returning a VenueList."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        data = json.load(f)
    _validate_schema(data, path)
    return _deserialize(data)


def _validate_schema(data: dict, path: Path) -> None:
    with open(_SCHEMA_PATH) as f:
        schema = json.load(f)
    try:
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as e:
        field_path = " -> ".join(str(p) for p in e.path)
        raise ConfigValidationError(
            f"Invalid config at {path}: {e.message}"
            + (f" (field: {field_path})" if field_path else "")
        ) from e


def _deserialize(data: dict) -> VenueList:
    venues = [
        Brewery(
            key=v["key"],
            name=v["name"],
            url=v["url"],
            parser_config=v.get("parser_config", {}),
        )
        for v in data["venues"]
    ]
    return VenueList(
        list_name=data["list_name"],
        venues=venues,
        target_repo=data["target_repo"],
        target_branch=data.get("target_branch", "main"),
        target_url=data.get("target_url"),
        template_dir=data.get("template_dir"),
    )
```

**`pyproject.toml`**: Add `"jsonschema>=4.0.0"` to `[project].dependencies`.

**`around_the_grounds/config/__init__.py`**: Verify exists; add exports for `VenueList`,
`load_venue_list`, `ConfigValidationError`.

**Testable**: `python -c "from around_the_grounds.config.loader import load_venue_list"`
**Depends on**: nothing (but note `Brewery` model must exist — it does today)
**Blocks**: WP02, WP03, WP04

---

### WP02 — Migrate `breweries.json`

File: `around_the_grounds/config/breweries.json`

1. Rename top-level `"breweries"` → `"venues"`
2. Add `"list_name": "Ballard Food Trucks"`
3. Add `"target_repo": "https://github.com/steveandroulakis/ballard-food-trucks.git"`
4. Add `"target_branch": "main"`
5. Add `"target_url": "https://ballard-food-trucks.vercel.app"` (informational)
6. Add `"source_type"` per venue:
   - HTML scrapers: `stoup-ballard`, `obec-brewing`, `wheelie-pop` → `"html"`
   - API/data scrapers: `yonder-balebreaker`, `urban-family`, `chucks-greenwood`, `salehs-corner` → `"api"`
7. Add `"timezone": "America/Los_Angeles"` to all venues
8. Omit `"template_dir"` — built-in `public_template/` is the default

**Note**: `source_type` is added to the schema but not yet consumed by parsers. The
registry still dispatches by `key`. This is schema metadata for spec 005's use.

**Depends on**: WP01 (schema must exist to validate the migrated file)
**Testable**: `python -c "from around_the_grounds.config.loader import load_venue_list; load_venue_list('around_the_grounds/config/breweries.json')"`

---

### WP03 — Update `main.py`

**3a. Remove import**:
```python
# Remove:
from .config.settings import get_git_repository_url
# Add:
from .config.loader import ConfigValidationError, VenueList, load_venue_list
```

**3b. Remove `load_brewery_config()` entirely.** Replace its single call site in
`async_main()` with a direct call to `load_venue_list(args.venues_config)`.

**3c. Add `_resolve_template_dir()` helper**:
```python
def _resolve_template_dir(venue_list: VenueList, config_path: str) -> Path:
    if venue_list.template_dir:
        return (Path(config_path).parent / venue_list.template_dir).resolve()
    return Path(__file__).parent.parent / "public_template"
```

**3d. Update `async_main()`** — load `venue_list` once, pass fields downstream:
```python
venue_list = load_venue_list(args.venues_config)
events, errors = await scrape_food_trucks(venue_list.venues)
...
if args.deploy:
    await deploy_to_web(events, errors, venue_list)
if args.preview:
    template_dir = _resolve_template_dir(venue_list, args.venues_config)
    await preview_locally(events, errors, template_dir)
```

**3e. Update `deploy_to_web()` signature**:
```python
async def deploy_to_web(events, errors, venue_list: VenueList) -> bool:
    repository_url = venue_list.target_repo
    target_branch = venue_list.target_branch
    template_dir = _resolve_template_dir(venue_list, ...)
    ...
    return _deploy_with_github_auth(web_data, repository_url, target_branch, template_dir)
```

**3f. Update `_deploy_with_github_auth()` signature**:
```python
def _deploy_with_github_auth(
    web_data: dict, repository_url: str, target_branch: str, template_dir: Path
) -> bool:
```
Replace `Path.cwd() / "public_template"` with `template_dir`.
Replace `["git", "push", "origin", "main"]` with `["git", "push", "origin", target_branch]`.

**3g. Update `preview_locally()` signature**:
```python
async def preview_locally(events, errors, template_dir: Path) -> bool:
```
Replace `Path.cwd() / "public_template"` with `template_dir`.

**3h. Update argparse in `main()`**:
```python
# Remove:
parser.add_argument("--config", "-c", ...)
parser.add_argument("--git-repo", ...)
# Add:
parser.add_argument("venues_config", help="Path to venues configuration JSON file")
```
`--deploy`, `--preview`, `--verbose`, `--version` unchanged.

`ConfigValidationError` and `FileNotFoundError` from `load_venue_list` propagate to the
existing outer `try/except` in `main()` — no new error handling code needed.

**Depends on**: WP01
**Blocks**: WP04, WP05

---

### WP04 — Update Temporal layer

**`temporal/shared.py`**:
- Remove `git_repository_url` field
- Remove `DEFAULT_GIT_REPOSITORY` import from `config.settings`
- `config_path: Optional[str] = None` → `config_path: str = ""`

**`temporal/activities.py`**:
- Replace `load_brewery_config` import from `main` with `load_venue_list` from `config.loader`
- `ScrapeActivities.load_brewery_config` activity: calls `load_venue_list(config_path)`, returns `venue_list.venues` serialized
- `DeploymentActivities.deploy_to_git`: accept `config_path` in payload instead of `repository_url`; call `load_venue_list(config_path)` to get `target_repo`, `target_branch`, `template_dir`; replace hardcoded `Path.cwd() / "public_template"` and `"main"` branch

**`temporal/workflows.py`**:
- Remove `params.git_repository_url` from the `deploy_to_git` activity payload
- Pass `config_path: params.config_path` instead

**`temporal/starter.py`**:
- Remove `--git-repo` flag and `get_git_repository_url()` call
- Replace `--config` optional flag with required positional `venues_config` arg
- Remove `git_repository_url=...` from `WorkflowParams(...)` constructor

**`temporal/schedule_manager.py`**:
- Replace `--config` optional with required positional `venues_config` arg
- Update `WorkflowParams(config_path=config_path)` accordingly

**Depends on**: WP01, WP03
**Blocks**: WP05

---

### WP05 — Update tests + CLAUDE.md

**`pyproject.toml`**: `jsonschema` must be added (done in WP01) and `uv sync --dev` run.

**`tests/conftest.py`**: Update `test_breweries_config` fixture to new schema shape —
rename to `test_venues_config`, add `list_name`, `target_repo`, rename key to `"venues"`,
add `source_type` per entry.

**`tests/fixtures/config/test_breweries.json`**: Update to new schema shape.

**`tests/integration/test_cli.py`** (most impacted):
- Remove `load_brewery_config` import
- All `main(["--config", path])` → `main([path])`
- All `main(["--config", path, "--verbose"])` → `main([path, "--verbose"])`
- `test_main_help_flag`: check for `"venues_config"` not `"--config"` in help text
- `test_main_default_config`: rewrite — `main([])` now exits with argparse error (code 2)
- `test_load_brewery_config_*` tests → `test_load_venue_list_*` (schema validation, missing fields)
- `test_scrape_food_trucks_no_breweries`: update empty venues fixture (schema requires `minItems: 1`)

**`tests/temporal/test_workflows.py`**:
- Remove `params.git_repository_url == DEFAULT_GIT_REPOSITORY` assertion
- Remove `DEFAULT_GIT_REPOSITORY` import

**`tests/temporal/test_activities.py`**:
- Update patching target from `load_brewery_config` to `load_venue_list`

**New: `tests/unit/test_config_loader.py`**:
- `load_venue_list` with valid config → correct `VenueList`
- Missing `target_repo` → `ConfigValidationError` with field in message
- Missing file → `FileNotFoundError`
- `target_branch` defaults to `"main"` when omitted
- `template_dir` resolved relative to config file location

**`CLAUDE.md`** — update "Running the Application":
```bash
# Before:
uv run around-the-grounds --deploy
uv run around-the-grounds --config /path/to/config.json --deploy

# After:
uv run around-the-grounds around_the_grounds/config/breweries.json
uv run around-the-grounds around_the_grounds/config/breweries.json --deploy
uv run around-the-grounds around_the_grounds/config/breweries.json --preview
uv run around-the-grounds /path/to/music-venues.json --deploy
```

**Depends on**: WP01–WP04
**Blocks**: nothing

---

## What Gets Removed

| Item | Location |
|---|---|
| `DEFAULT_GIT_REPOSITORY` | `config/settings.py` |
| `get_git_repository_url()` | `config/settings.py` |
| `--git-repo` CLI flag | `main.py`, `temporal/starter.py` |
| `GIT_REPOSITORY_URL` env var check | `config/settings.py` (via `get_git_repository_url`) |
| `--config` / `-c` flag | `main.py`, `temporal/starter.py`, `temporal/schedule_manager.py` |
| `load_brewery_config()` function | `main.py` |
| `git_repository_url` field | `temporal/shared.py` `WorkflowParams` |
| `"breweries"` top-level key | `config/breweries.json` |
| Hardcoded `Path.cwd() / "public_template"` | `main.py` (×2), `temporal/activities.py` |
| Hardcoded `"main"` branch in git push | `main.py`, `temporal/activities.py` |

`settings.py` is **not deleted** — `VisionConfig` and `VisionConfig.from_env()` remain.

## What Stays

- `--deploy`, `--preview`, `--verbose` flags
- `Brewery` model — unchanged; `VenueList.venues` is `List[Brewery]`
- All parser/scraper logic
- `generate_web_data()` function
- `ANTHROPIC_API_KEY` env var (used by vision + haiku)
- Core git deploy logic in `_deploy_with_github_auth()` — signature changes, logic unchanged
- Temporal workflow structure (`FoodTruckWorkflow`, activities classes)
- GitHub App auth

## Dependency Order

```
WP01 (schema + loader)
  └─→ WP02 (migrate breweries.json)
  └─→ WP03 (main.py)
        └─→ WP04 (temporal layer)
              └─→ WP05 (tests + docs)
```

WP02 and WP03 can be developed in parallel after WP01.

## Upstream PR Notes

**Title**: `feat: config file owns deployment target (spec 006)`

**Summary**:
- Adds `config/loader.py` with `load_venue_list()`, `VenueList` dataclass, and JSON Schema validation
- Migrates `breweries.json`: `"breweries"` → `"venues"`, adds `list_name`, `target_repo`, `target_branch`, `target_url`, `source_type`/`timezone` per venue
- CLI: `--config`/`--git-repo` removed; replaced by required positional `venues_config`
- `DEFAULT_GIT_REPOSITORY`, `get_git_repository_url()`, `GIT_REPOSITORY_URL` removed
- `template_dir` and `target_branch` threaded from config through deploy + preview paths
- Temporal `WorkflowParams` drops `git_repository_url`
- Adds `jsonschema>=4.0.0` dependency

**Reviewer checklist**:
1. `grep -r "DEFAULT_GIT_REPOSITORY\|get_git_repository_url\|GIT_REPOSITORY_URL" around_the_grounds/` → zero matches
2. `grep -r "Path.cwd.*public_template" around_the_grounds/` → zero matches
3. `grep -rn '"main"' around_the_grounds/` — verify no hardcoded branch strings remain in git push calls
4. `Brewery` model diff is empty
5. `parsers/registry.py` diff is empty
6. `source_type` in `breweries.json` is schema-only metadata — parsers still dispatch via registry key, not `source_type`
7. `settings.py` still exists (not deleted); only `DEFAULT_GIT_REPOSITORY` and `get_git_repository_url` removed
