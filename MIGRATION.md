# Migration Guide — Multi-Site Merge

This guide is for maintainers pulling the **multi-site merge** into an existing checkout. It describes what changes, what doesn't, and what each maintainer should (and should not) do after pulling.

**Short version:** Both maintainers can pull and keep going. No forced migration work, no new required env variables, no new secrets, no target-repo changes. The sections below cover edge cases and recommended follow-ups.

> **⚠️ Status note (post-`feature/unify-temporal-deploy`):** The follow-up #1/#2 work (unify Temporal with the CLI deploy path; retire `config/breweries.json`) is now **DONE**. As a result, several statements in the body of this guide that describe the legacy Temporal-via-`breweries.json` path are now historically accurate but no longer reflect current `main`. Look for **`UPDATE:`** notes inline. See ["After Phase 7 — suggested follow-up work"](#after-phase-7--suggested-follow-up-work-not-blockers) for the new state.

---

## TL;DR by maintainer

| Concern | Steve (Ballard) | jredding (Brooklyn) |
|---|---|---|
| Target repo URL | Unchanged (`steveandroulakis/ballard-food-trucks`) | Unchanged per site (`jredding/atg-*`) |
| Deploy strategy | Unchanged (clone + `public/` subdir → Vercel) | Unchanged (`git init` + force-push to root → GitHub Pages) |
| CLI invocation | `uv run around-the-grounds --deploy` still works; explicit `--site ballard-food-trucks --deploy` recommended | `uv run around-the-grounds --site <key> --deploy` unchanged |
| Env variables | Unchanged; two new **optional** variables for haiku weather location | Unchanged |
| Scheduled worker | Works as-is via the legacy config loader | Works as-is via the CLI subprocess path |
| Tests | 499 passing (was 196 on Steve's main / 358 on jredding's) | 499 passing |
| Templates | `public_templates/food-trucks/index.html` now has the clickable brewery-search feature | `public_templates/{music,kids}/index.html` unchanged |
| Known regression risk | None — verified byte-for-byte parity against live production `data.json` in Phase 5 | None for the three Brooklyn sites; see below for the `ballard-food-trucks` "control" site case |

---

## For Steve (Ballard) — merging this into `main`

### What actually changes

1. **Your Temporal worker path is unchanged.** The `FoodTruckWorkflow` → `load_brewery_config(None)` activity still reads `config/breweries.json`, and `breweries.json` now mirrors your pre-merge `main` version byte-for-byte: 9 venues, Urban Family pointing at the WordPress Sugar Calendar primary source. The `deploy_to_git` activity still clones your target repo, scoped-adds to `public/`, and normal-pushes. Same behavior, same result, same target. **No Temporal changes required.**

   > **UPDATE (post-unification):** The Temporal worker now reads `config/sites/ballard-food-trucks.json` via a new `load_site` activity (workflow resolves missing `site_key` to `"ballard-food-trucks"` for back-compat with the persisted schedule). `deploy_to_git` is now a thin shim that calls `main.py:_deploy_with_github_auth` with `deploy_subdir="public"` from the site config. Commits now show `Around the Grounds Bot <bot@around-the-grounds.app>` instead of your personal identity. `config/breweries.json` is deleted.

2. **A new CLI surface is available but not required.** You can now run `uv run around-the-grounds --site ballard-food-trucks --preview` or `--deploy` and it goes through the new site-aware path (reads `config/sites/ballard-food-trucks.json`, respects `deploy_subdir: "public"`). You can also run `uv run around-the-grounds --deploy` with no flag and it defaults to `ballard-food-trucks`. Both routes produce the same end result as your legacy Temporal path because the configs match.

3. **No env variables change.** `ANTHROPIC_API_KEY`, `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY_B64`, `GIT_REPOSITORY_URL`, `TEMPORAL_ADDRESS`, etc. all keep the same names and meanings. `DEFAULT_GIT_REPOSITORY` in `config/settings.py` is still `https://github.com/steveandroulakis/ballard-food-trucks.git`.

4. **New *optional* env variables for haiku weather location:** `WEATHER_LOCATION_LAT` and `WEATHER_LOCATION_LON`. Defaults are Ballard, Seattle. You only need to set these if you want to override the location. Weather itself is fetched from Open-Meteo which requires no API key.

5. **Cosmetic `data.json` shape changes** you may notice on the first post-merge deploy. The template ignores all of these, so there is no visual change on ballardfoodtrucks.com:
   - New top-level fields: `site_name`, `site_key`, `timezone_label`, `timezone_note` (added)
   - Top-level `timezone` field changed meaning: was `"PT"`, now `"America/Los_Angeles"` (IANA)
   - Per-event: new `title` (mirrors `vendor`), `venue` (mirrors `location`), `extraction_method` (now always present)
   - Per-event: removed `timezone: "PT"` (never read by the template)
   - Verified in Phase 5: diffed against the live production `data.json` — zero content mismatches across all 47 events.

6. **CLI invocation:** your existing `uv run around-the-grounds --deploy` still works (defaults to `ballard-food-trucks`). If you want to be explicit — and we recommend this — use `uv run around-the-grounds --site ballard-food-trucks --deploy`.

### Things you should do after pulling (recommended, not required)

These are low-effort hygiene steps that catch common post-merge surprises:

- [ ] **Re-run `uv sync --dev`** to confirm your venv matches `uv.lock`. No new dependencies were added, but this is a good sanity check.
- [ ] **Run the full test suite** and confirm `499 passed, 1 skipped, 0 failed`:
  ```bash
  uv run python -m pytest -q
  ```
- [ ] **Generate a local preview and eyeball it**:
  ```bash
  uv run around-the-grounds --site ballard-food-trucks --preview
  cd public && python -m http.server 8000
  ```
  Visit `http://localhost:8000` and confirm all 9 venues render with expected events.
- [ ] **Read the new `deploy_subdir` abstraction** in [CLAUDE.md](./CLAUDE.md#deployment-strategies) and [ARCHITECTURE.md](./ARCHITECTURE.md). This is the key design change you need to be aware of. If you ever create additional sites or change Ballard's deploy target, you need to understand which strategy applies.
- [ ] **Audit `config/sites/ballard-food-trucks.json`** once after merge. It should have:
  - `target_repo: "https://github.com/steveandroulakis/ballard-food-trucks.git"`
  - `deploy_subdir: "public"`
  - 9 venues, with `urban-family` pointing at `https://urbanfamilybrewing.com/home/calendar/`
- [ ] ~~**Do not delete `config/breweries.json`.**~~ **Obsolete (post-unification):** `breweries.json` and the legacy activities have been deleted in `feature/unify-temporal-deploy`. The Temporal worker now reads `config/sites/ballard-food-trucks.json` directly via the `load_site` activity. There is no longer a dual-config sync responsibility.

### Things you should NOT do

- ~~**Do not** delete `config/breweries.json`.~~ **Obsolete (post-unification):** breweries.json is deleted; the Temporal worker no longer depends on it.
- **Do not** change `deploy_subdir` on `config/sites/ballard-food-trucks.json` to `""`. That would switch Ballard to root-mode deploy (fresh init + force-push) which would wipe your target repo's history and break Vercel's subdir expectations. Post-unification: `deploy_subdir` is now honored by both the CLI and the Temporal worker, so a wrong value here will affect *all* runs.
- **Do not** remove `around_the_grounds/utils/weather.py`. Even though it's only actively used by Ballard's haiku generation, it's imported by the haiku module unconditionally.

### After Phase 7 — suggested follow-up work (not blockers)

These are things worth doing in a separate PR after the main merge lands. They're all optional.

> **Status update:** Follow-ups #1 and #2 are now **DONE** (see "Done in `feature/unify-temporal-deploy`" below). Items #3, #4, #5 remain latent; new items F-A and F-B were surfaced by the unification work and are tracked here.

#### Done in `feature/unify-temporal-deploy`

1. ✅ **Unify the Temporal deploy path with the CLI deploy path.** `around_the_grounds/temporal/activities.py:deploy_to_git` is now a thin shim that delegates to `main.py:_deploy_with_github_auth(web_data, site.target_repo, site.template, site.deploy_subdir)`. The hardcoded `repo_dir / "public"` and personal git author config are gone; commits now carry `Around the Grounds Bot <bot@around-the-grounds.app>` (matching the CLI / jredding's sites). `deploy_subdir` is honored end-to-end.

2. ✅ **Migrate the Temporal worker off `breweries.json`.** A new `load_site` activity returns a serializable `SiteConfig` dict; the workflow carries `site_key: Optional[str]` in `WorkflowParams` (default `None` resolves to `"ballard-food-trucks"` inside the workflow so the persisted Temporal schedule keeps firing without modification). `config/breweries.json` and the `load_brewery_config` / `scrape_food_trucks` legacy wrappers are deleted. The latent dual-config drift risk is gone — adding a venue to `config/sites/ballard-food-trucks.json` is now the only place to change venues for both Temporal and CLI runs.

#### Still latent (deferred to follow-up PRs)

3. **Fix the pre-existing `extraction_method: 'vision'` template contract on the other per-site templates.** For `food-trucks/`, `generate_web_data` in `main.py` shims the JSON output from `"ai-vision"` to `"vision"` so the template's `=== 'vision'` check works. The Temporal path now inherits this shim for free (since it routes through `main.py:generate_web_data`). If the music or kids templates ever add AI-vision extraction in the future, they'll need the same check (or the shim should become template-aware). Not urgent because those sites don't use vision today.

4. **Make the haiku prompt per-site.** Right now there's one `config/haiku_prompt.txt` and it's Ballard-specific (references "Seattle's Ballard neighborhood"). If a non-Ballard site ever opts into haikus via `generate_description: true`, it'll need a per-site prompt override. A cleaner design would be a `haiku_prompt_file` field in `SiteConfig`, or convention-based `config/sites/<key>/haiku_prompt.txt`. Not urgent; nobody needs it right now.

5. **Re-run the Phase 5 parity verification after a production Temporal worker cycle.** Partially satisfied by Phase E gates 4-5 of `feature/unify-temporal-deploy`, which ran the new Temporal path against a test task queue and a real deploy to `steveandroulakis/ballard-food-trucks`, byte-comparing the resulting live `data.json` against a local `--preview`. Worth re-running periodically to catch any future drift.

#### New follow-ups surfaced by `feature/unify-temporal-deploy`

F-A. **Per-site weather location.** `WEATHER_LOCATION_LAT` / `WEATHER_LOCATION_LON` are global env vars defaulting to Ballard. Site-level concerns are now nicely encapsulated in `SiteConfig` for everything *except* weather coordinates. When a non-Ballard site opts into haikus, these should become per-site fields on `SiteConfig` (e.g. `weather_lat: Optional[float]`, `weather_lon: Optional[float]`). Until then they remain env-var globals.

F-B. **`scrape_single_venue` does not pass timezone.** The CLI's `scrape_site` calls `coordinator.scrape_all(site.venues, timezone=site.timezone)`, but the Temporal workflow's per-venue `scrape_single_venue` activity calls `coordinator.scrape_one(venue)` with no timezone argument. This is a pre-existing gap not introduced by the unification work, but it means timezone-aware time parsing at scrape time only flows through the CLI path, not Temporal. Worth fixing in a follow-up that either threads `site.timezone` through `scrape_single_venue` (preferred — keeps the parallel-batch pattern) or collapses scraping back into a single `scrape_all` activity.

---

## For jredding (Brooklyn) — merging this into his fork

### What works as-is

1. **All three Brooklyn sites (`park-slope-music`, `childrens-events`, `ballard-food-trucks` if he still runs it as a control) continue to work unchanged** via the Cloud Run job → `uv run around-the-grounds --site <key> --deploy` path. Each reads its own `config/sites/<key>.json` with `deploy_subdir` defaulting to `""`, and follows the `git init` + force-push flow.

2. **A new `deploy_subdir` field exists on `SiteConfig` with default `""`.** His existing three site configs don't need to add it. The loader uses `data.get("deploy_subdir", "")` so "missing" == "empty" == root mode. He can add `"deploy_subdir": ""` explicitly in his configs if he wants self-documentation, but functionally it changes nothing.

3. **`config/sites/{park-slope-music,childrens-events}.json` are unchanged.** No venue changes, no URL changes, no parser_config changes.

4. **The GCP Artifact Registry GitHub Actions workflow is unchanged.** His Docker build/push pipeline continues to work.

### What changes that's worth knowing about

1. **`config/sites/ballard-food-trucks.json` gets overwritten by Steve's version.** It now points at `steveandroulakis/ballard-food-trucks`, uses `deploy_subdir: "public"`, and includes Steve's full 9-venue list (adds `channel-marker`, `lucky-envelope`, and updates `urban-family`'s URL to the WordPress Sugar Calendar primary source). If jredding uses `ballard-food-trucks` as a "control" site to verify his changes don't break Ballard's scrape, he has three options:
   - **(a) Run it without `--deploy`**: use `--preview` or plain `uv run around-the-grounds --site ballard-food-trucks` so the scrape + render still happens but nothing deploys. This turns it into a scrape-level regression control. **Recommended** — the scrape layer is where control-site testing has the most value anyway.
   - **(b) Override the deploy target**: `--git-repo https://github.com/jredding/atg-ballard-food-trucks.git` to push to his own target repo. Note that `deploy_subdir: "public"` still applies, so the clone + scoped-add strategy runs. His `atg-ballard-food-trucks` target repo would need a `public/` subdir structure to match, or the first deploy would create one alongside whatever's at the root.
   - **(c) Maintain a private ballard-control config** on a long-lived feature branch in his fork.

2. **`config/breweries.json` is now Steve's 9-venue version.** This file is only read by the legacy Temporal activities. If jredding runs Temporal locally for development with `config_path=None`, the default will be the Ballard 9-venue list. This matters only for local Temporal dev — his production Cloud Run path invokes the CLI directly and is unaffected.

   > **UPDATE (post-unification):** `breweries.json` and the legacy activities are deleted. The Temporal `FoodTruckWorkflow` now resolves `site_key=None` to `"ballard-food-trucks"` internally and reads `config/sites/ballard-food-trucks.json`. If jredding wants to run Temporal locally against a Brooklyn site, he can pass `WorkflowParams(site_key="park-slope-music", ...)` instead.

3. **The haiku generator is now weather-grounded with a Ballard-specific prompt.** His three sites have `generate_description: false`, so haikus never run for them. But if he ever wants to enable haikus for a Brooklyn site:
   - Set `generate_description: true` in the site config
   - Override `config/haiku_prompt.txt` via `HAIKU_PROMPT_FILE` env var to a Brooklyn-appropriate prompt (the built-in prompt explicitly references "Seattle's Ballard neighborhood")
   - Set `WEATHER_LOCATION_LAT` / `WEATHER_LOCATION_LON` env vars for Brooklyn coordinates (default is Ballard)

4. **New modules exist but aren't used by his sites:**
   - `around_the_grounds/utils/weather.py` (Open-Meteo fetcher)
   - `around_the_grounds/parsers/channel_marker.py` (Google Sheets CSV)
   - `around_the_grounds/parsers/lucky_envelope.py` (Squarespace embedded JSON)
   - All are imported by `registry.py` and exercised by tests. **Do not delete them** — removing any of them breaks the test suite.

5. **Docs have been rewritten.** `CLAUDE.md`, `README.md`, `DEPLOYMENT.MD`, `WEB-DEPLOYMENT.md`, `ARCHITECTURE.md`, `HAIKU-GENERATOR.md`, `ADDING-VENUES.md`, `TESTING.md` all reflect the joint-maintenance reality (Ballard via Vercel subdir, Brooklyn via GH Pages root). If jredding has in-flight doc edits on feature branches, there may be merge conflicts in these files. They're usually easy to resolve — most changes are additive.

### Things jredding should NOT do

- ~~**Do not** delete `config/breweries.json`.~~ **Obsolete (post-unification):** breweries.json is deleted and `from around_the_grounds.main import load_brewery_config` no longer exists. There is nothing to preserve.
- **Do not** delete `around_the_grounds/utils/weather.py`, `around_the_grounds/parsers/channel_marker.py`, or `around_the_grounds/parsers/lucky_envelope.py`. They're imported by `registry.py` and tests.
- **Do not** change `deploy_subdir` on the three existing Brooklyn site configs. They expect root-mode (default `""`) behavior.
- **Do not** expect `config/sites/ballard-food-trucks.json` to push to his own target repo — it now points at Steve's. Use `--git-repo` override if needed.

---

## Common to both

- **Python version:** unchanged (3.8+ required)
- **Dependencies:** no new production deps. `uv.lock` may differ slightly but resolves to the same versions in practice. Run `uv sync --dev` after merge to verify.
- **Target repo access:** unchanged — same GitHub App, same installations
- **Secrets:** unchanged
- **Test suite:** `499 passed, 1 skipped, 0 failed` on both sides after merge
- **Pre-existing haiku integration test failure** that was on jredding's tree before the merge is **fixed** by Phase 3 (the test now patches `ANTHROPIC_API_KEY` and `fetch_weather` correctly)

---

## If something goes wrong after pulling

1. **Preview works but deploy fails with clone errors**: your GitHub App may not have Contents: Read & Write on the target repo. Check the App installation.
2. **Deploy succeeds but website doesn't update**: check the target repo's commit log — the bot commit should appear within seconds. If it doesn't, check `--verbose` output for GitHub App auth errors.
3. **Test suite fails** after pull: run `uv sync --dev` first, then `uv run python -m pytest -v` and compare to the expected `499 passed, 1 skipped`. Any failures are likely the result of a bad merge, not a real regression — the full suite is green on `feature/multi-site-merge`.
4. **Preview shows 0 events from a specific venue**: that venue's website may have changed structure since the parser was last updated. Run `uv run around-the-grounds --site ballard-food-trucks --verbose` and look for parser-specific error messages. This is not a merge regression — the parsers are identical to the pre-merge tree.
5. **Haiku generation silently stops working**: verify `ANTHROPIC_API_KEY` is set AND Open-Meteo is reachable. The weather fetch is a hard prerequisite now. If Open-Meteo is down or your network blocks it, the haiku generator returns `None` and the rest of the pipeline continues normally.

---

## Related documents

- [CLAUDE.md](./CLAUDE.md) — full architecture and component overview
- [README.md](./README.md) — user-facing overview and quick start
- [ARCHITECTURE.md](./ARCHITECTURE.md) — system diagrams, data models, deployment topology
- [DEPLOYMENT.MD](./DEPLOYMENT.MD) — GitHub App config and the two deploy strategies
- [WEB-DEPLOYMENT.md](./WEB-DEPLOYMENT.md) — deployment workflow and troubleshooting
- [HAIKU-GENERATOR.md](./HAIKU-GENERATOR.md) — weather-grounded haiku configuration
- [ADDING-VENUES.md](./ADDING-VENUES.md) — generic vs venue-specific parser decision tree and site creation guide
