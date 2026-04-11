# Tasks: 006 — Multi-Config Deployment

## WP01 — JSON Schema + config loader
lane: planned
depends_on: []
blocked_by_feature: 004-generic-models

### Subtasks
- [ ] Add `jsonschema>=4.0.0` to `pyproject.toml` dependencies
- [ ] Create `around_the_grounds/config/schemas/food-trucks-config.schema.json`
- [ ] Create `around_the_grounds/config/loader.py` with `VenueList`, `load_venue_list()`, `ConfigValidationError`
- [ ] Update `around_the_grounds/config/__init__.py` to export new symbols
- [ ] Run `uv sync --dev` to install jsonschema

### Acceptance
- `python -c "from around_the_grounds.config.loader import load_venue_list, VenueList"` succeeds
- `jsonschema` importable

---

## WP02 — Migrate breweries.json
lane: planned
depends_on: [WP01]

### Subtasks
- [ ] Rename top-level `"breweries"` → `"venues"`
- [ ] Add `"list_name"`, `"target_repo"`, `"target_branch"`, `"target_url"` fields
- [ ] Add `"source_type"` to each venue (html or api per parser type)
- [ ] Add `"timezone": "America/Los_Angeles"` to each venue
- [ ] Validate: `python -c "from around_the_grounds.config.loader import load_venue_list; load_venue_list('around_the_grounds/config/breweries.json')"`

### Acceptance
- Config file loads without `ConfigValidationError`
- All 7 venues present with correct `source_type`

---

## WP03 — Update main.py
lane: planned
depends_on: [WP01]

### Subtasks
- [ ] Remove `load_brewery_config()` function; replace with `load_venue_list()` call
- [ ] Add `_resolve_template_dir(venue_list, config_path)` helper
- [ ] Update `deploy_to_web()` to accept `VenueList` instead of `git_repo_url`
- [ ] Update `_deploy_with_github_auth()` signature: add `target_branch`, `template_dir` params
- [ ] Update `preview_locally()` signature: add `template_dir` param
- [ ] Replace hardcoded `Path.cwd() / "public_template"` (×2) with `template_dir`
- [ ] Replace hardcoded `"main"` branch in git push with `target_branch`
- [ ] Update argparse: remove `--config`/`-c` and `--git-repo`; add positional `venues_config`
- [ ] Remove `from .config.settings import get_git_repository_url` import

### Acceptance
- `uv run around-the-grounds --help` shows `venues_config` positional arg
- `uv run around-the-grounds --help` does NOT show `--config` or `--git-repo`

---

## WP04 — Update Temporal layer
lane: planned
depends_on: [WP01, WP03]

### Subtasks
- [ ] `temporal/shared.py`: remove `git_repository_url` field; remove `DEFAULT_GIT_REPOSITORY` import
- [ ] `temporal/activities.py`: replace `load_brewery_config` with `load_venue_list`; update `deploy_to_git` to load config from path
- [ ] `temporal/workflows.py`: remove `params.git_repository_url` from deploy payload
- [ ] `temporal/starter.py`: remove `--git-repo` flag; replace `--config` with positional arg
- [ ] `temporal/schedule_manager.py`: replace `--config` optional with positional arg

### Acceptance
- No references to `DEFAULT_GIT_REPOSITORY` in temporal/
- No references to `git_repository_url` in temporal/

---

## WP05 — Tests + CLAUDE.md
lane: planned
depends_on: [WP02, WP03, WP04]

### Subtasks
- [ ] Update `tests/conftest.py` `test_breweries_config` fixture to new schema shape
- [ ] Update `tests/fixtures/config/test_breweries.json` to new schema shape
- [ ] Update `tests/integration/test_cli.py`: all `--config` → positional, remove `load_brewery_config` import
- [ ] Update `tests/temporal/test_workflows.py`: remove `git_repository_url` assertions
- [ ] Update `tests/temporal/test_activities.py`: patch `load_venue_list` instead of `load_brewery_config`
- [ ] Create `tests/unit/test_config_loader.py` with loader unit tests
- [ ] Update `CLAUDE.md` running commands to new CLI syntax
- [ ] Run: `grep -r "DEFAULT_GIT_REPOSITORY\|get_git_repository_url\|GIT_REPOSITORY_URL" around_the_grounds/` → zero matches
- [ ] Run: `grep -r "Path.cwd.*public_template" around_the_grounds/` → zero matches

### Acceptance
- `uv run python -m pytest` — all tests pass
- Both grep audits return zero matches
