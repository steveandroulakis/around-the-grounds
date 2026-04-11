# Around the Grounds 🍺🎫

A multi-site event aggregator written in Python. Each site you want to publish is described by a single JSON config file in `config/sites/`. The CLI scrapes the configured venues, generates a static site, and pushes it to a GitHub-hosted target repo. **You can use this codebase to publish your own event site without writing parser code, as long as the venues you want to track use platforms the generic parsers already understand** (WordPress, HTML with CSS selectors, AJAX/JSON APIs, JSON-LD).

## Live sites running on this codebase

Three sites publish from this repo today, on three different host setups, all from the same code:

| Site | Live URL | Hosting | Updates |
|---|---|---|---|
| **Food Trucks in Ballard** | <https://www.ballardfoodtrucks.com> | Vercel (watches `public/` subdir of [`steveandroulakis/ballard-food-trucks`](https://github.com/steveandroulakis/ballard-food-trucks)) | Self-hosted Temporal worker, hourly |
| **Park Slope Music** | <https://jredding.github.io/atg-park-slope-music/> | GitHub Pages from [`jredding/atg-park-slope-music`](https://github.com/jredding/atg-park-slope-music) repo root | Google Cloud Run Job, daily |
| **Brooklyn Children's Events** | <https://jredding.github.io/atg-childrens-events/> | GitHub Pages from [`jredding/atg-childrens-events`](https://github.com/jredding/atg-childrens-events) repo root | Google Cloud Run Job, daily |

The Ballard site adds AI haikus (Claude Sonnet 4.6, grounded in real-time weather from Open-Meteo) and AI vision analysis (Claude Vision API) for vendor names extracted from food-truck logo posts where text scraping isn't enough.

## What it does

When you run `uv run around-the-grounds --site <key> --deploy`, the CLI:

1. **Scrapes** every venue listed in `config/sites/<key>.json` concurrently. Each venue is parsed by either a generic platform parser or a venue-specific parser registered for it.
2. **Optionally generates AI content** when `ANTHROPIC_API_KEY` is set: a daily haiku for the site (if the site opts in via `generate_description: true`) and AI vision analysis for venues whose parsers ask for it.
3. **Renders** the site by copying `public_templates/<template>/` into the target repo (at the repo root or into a `deploy_subdir`, depending on the site config) and writing a fresh `data.json` next to it.
4. **Pushes** to the target GitHub repo using a GitHub App for authentication. Two deploy strategies are selected automatically by the site config:
   - `deploy_subdir: ""` (default) → fresh `git init` + force-push, rewriting the target repo's history. Used by GitHub-Pages-served sites that own the whole target repo.
   - `deploy_subdir: "public"` (or any non-empty value) → `git clone` + scoped `git add <subdir>/` + normal push, preserving the rest of the target repo. Used when a host like Vercel watches a subdirectory.

The same code powers both manual one-off runs (CLI) and scheduled production runs (Temporal worker or Cloud Run Job). Scheduled runs invoke the same workflow / activities as the CLI; there is no parallel implementation.

## Quick start

### Install

```bash
git clone https://github.com/steveandroulakis/around-the-grounds
cd around-the-grounds
uv sync
```

### Run an existing site locally (no GitHub App needed)

```bash
# Show the next 7 days of events for the default site (Ballard food trucks)
uv run around-the-grounds

# Run a specific site
uv run around-the-grounds --site park-slope-music
uv run around-the-grounds --site childrens-events

# Run all configured sites
uv run around-the-grounds --site all

# Generate a local preview website in public/ that you can serve
uv run around-the-grounds --site ballard-food-trucks --preview
cd public && python -m http.server 8000   # then open http://localhost:8000
```

### Example output

```
🍺 Around the Grounds
==================================================
Found 47 events:

🎋 Today's Haiku:
🍂 Autumn mist rolls in—
Plaza Garcia's warmth glows
at Obec's wood door 🍺

📅 Saturday, April 11, 2026
  🎫 Johnson BBQ Provisions @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🎫 Kaosamai Thai @ Obec Brewing 04:00 PM - 08:00 PM
  🎫 TOLU 🖼️🤖 @ Urban Family Brewing 01:00 PM - 07:00 PM
```

The 🖼️🤖 marker on a vendor name means the vendor was identified by Claude Vision rather than text extraction.

## Build your own site

The fastest way to publish a new event site with this codebase is to add a new site config and reuse the existing generic parsers. You should not need to write any Python.

### 1. Pick a site key, target repo, and deploy strategy

- **Site key**: a stable slug, e.g. `seattle-trivia-nights`. This becomes the filename in `config/sites/`.
- **Target repo**: a dedicated GitHub repo that will hold the published static site. Create it empty.
- **Deploy strategy**:
  - **GitHub Pages from repo root** → set `deploy_subdir: ""` (or omit it). The target repo will be force-pushed each run.
  - **A host like Vercel that watches a subdirectory** → set `deploy_subdir: "public"`. The target repo's other files at root are preserved.

### 2. Create the site config

Create `around_the_grounds/config/sites/<your-site-key>.json`. Cribbing from `park-slope-music.json` or `childrens-events.json` is the easiest start:

```json
{
  "key": "seattle-trivia-nights",
  "name": "Seattle Trivia Nights",
  "template": "music",
  "timezone": "America/Los_Angeles",
  "target_repo": "https://github.com/yourname/seattle-trivia-nights.git",
  "generate_description": false,
  "deploy_subdir": "",
  "venues": [
    {
      "key": "the-pub",
      "name": "The Pub",
      "url": "https://thepub.example.com/events",
      "source_type": "wordpress",
      "parser_config": {
        "category_slug": "trivia"
      }
    }
  ]
}
```

The supported `source_type` values are `wordpress`, `html` (CSS selectors), `ajax` (JSON API), and `json-ld` (schema.org JSON-LD). Each has its own `parser_config` shape — see [ADDING-VENUES.md](./ADDING-VENUES.md) for the field-by-field reference and examples for each platform.

If a venue uses a platform none of these handle, you can add a venue-specific parser in `around_the_grounds/parsers/` and register it in `parsers/registry.py`. There are nine such hand-written parsers already in the repo (Stoup, Yonder/Bale Breaker, Obec, Urban Family, Wheelie Pop, Chuck's, Saleh's, Channel Marker, Lucky Envelope) you can use as templates.

### 3. (Optional) Customize the template

`public_templates/` holds one directory per template. Copying an existing one (`food-trucks/`, `music/`, `kids/`) and tweaking the HTML/CSS is the easiest path. The template reads from `data.json` written next to it; see any existing template's `index.html` for the available fields.

### 4. Preview locally

```bash
uv run around-the-grounds --site seattle-trivia-nights --preview
cd public && python -m http.server 8000
```

If the venues scrape and the template renders correctly, you're ready to deploy.

### 5. Set up the GitHub App and deploy

See **Web deployment** below.

## Web deployment

Web deployment uses a GitHub App for authentication. You only need to set this up once even if you publish multiple sites — the same App can be installed on each target repo.

### GitHub App setup

1. Create a GitHub App at <https://github.com/settings/apps>.
   - Repository permissions: **Contents (Read & Write)**, **Metadata (Read)**.
   - Generate and download a private key (a `.pem` file).
   - Install the App on every target repository it should be able to push to.
2. Base64-encode the private key:

   ```bash
   base64 -w0 your-app.private-key.pem    # Linux
   base64 your-app.private-key.pem        # macOS
   ```
3. Create a `.env` file (or set environment variables) with:

   ```
   GITHUB_APP_ID=123456
   GITHUB_CLIENT_ID=your-github-client-id
   GITHUB_APP_PRIVATE_KEY_B64=<the base64 string from step 2>
   ```
4. Deploy:

   ```bash
   uv run around-the-grounds --site <your-site-key> --deploy
   ```

Commits land on the target repo's `main` branch authored by `Around the Grounds Bot <bot@around-the-grounds.app>`. GitHub Pages or your hosting provider takes it from there.

For full deployment details, GitHub App permissions, and troubleshooting, see [DEPLOYMENT.MD](./DEPLOYMENT.MD) and [WEB-DEPLOYMENT.md](./WEB-DEPLOYMENT.md).

## Scheduled updates

You don't need scheduled updates to use this project — you can re-run `--deploy` from any machine, by hand or from `cron`. The two scheduling options below are what the live sites use, and either works for whatever you publish.

### Option A: Temporal worker (used by Ballard)

A self-hosted Temporal worker container that connects to a Temporal server (Temporal Cloud, a self-hosted server, or a local dev server) and listens on a task queue for scheduled `FoodTruckWorkflow` runs.

```bash
# Start the worker locally
uv run python -m around_the_grounds.temporal.worker
```

The workflow takes a `WorkflowParams(deploy: bool, site_key: Optional[str], ...)` payload. When `site_key` is omitted it defaults to `"ballard-food-trucks"` for back-compat with the original Ballard schedule; new schedules for other sites should pass the explicit site key. The bundled `schedule_manager.py` helper currently only creates Ballard-defaulted schedules — for non-Ballard sites, create the schedule directly via `temporal schedule create` or Temporal Cloud's UI and pass the workflow input as `{"deploy": true, "site_key": "your-site-key"}`.

See [SCHEDULES.md](./SCHEDULES.md) for the bundled schedule management commands and [around_the_grounds/temporal/README.md](./around_the_grounds/temporal/README.md) for the worker / Temporal Cloud setup.

For production, the Ballard site runs the worker as a Docker container managed by Watchtower: a push to `main` triggers the Docker Hub workflow in `.github/workflows/docker-build-push-dockerhub.yml`, Watchtower auto-pulls the new `:latest` tag, the worker restarts, and the next scheduled tick runs the new code.

### Option B: Google Cloud Run Job (used by the Brooklyn sites)

One Cloud Run Job per site, triggered by Cloud Scheduler on whatever cadence you want. Each job runs:

```sh
uv run around-the-grounds --site <site-key> --deploy
```

The Docker image is built and pushed by the GCP Artifact Registry workflow in `.github/workflows/docker-build-push.yml`.

## Configuration reference

### Site config fields (`config/sites/<key>.json`)

| Field | Required | Default | Notes |
|---|---|---|---|
| `key` | ✓ | — | Stable slug; must match the filename without `.json` |
| `name` | ✓ | — | Human-readable site name shown in `data.json` and commit messages |
| `template` | ✓ | — | Subdirectory of `public_templates/` to use |
| `timezone` | ✓ | — | IANA timezone (e.g. `America/Los_Angeles`) |
| `target_repo` | recommended | `""` | HTTPS URL of the target GitHub repo |
| `deploy_subdir` | optional | `""` | Empty → root mode (force-push). Non-empty → subdir mode (clone + scoped add) |
| `generate_description` | optional | `true` | Set to `false` to opt out of AI haiku generation |
| `venues` | ✓ | — | List of venue objects (see below) |

### Venue config fields

| Field | Required | Notes |
|---|---|---|
| `key` | ✓ | Stable slug, used by the parser registry |
| `name` | ✓ | Display name |
| `url` | ✓ | URL the parser fetches |
| `source_type` | optional | `wordpress`, `html`, `ajax`, `json-ld`, or omitted to use a venue-specific parser registered by `key` |
| `parser_config` | optional | Parser-specific configuration. See [ADDING-VENUES.md](./ADDING-VENUES.md) |

### Environment variables

```bash
# Required for web deployment
GITHUB_APP_ID=123456
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_APP_PRIVATE_KEY_B64=<base64-encoded private key>

# Optional: AI features (vision + haiku)
ANTHROPIC_API_KEY=sk-ant-...

# Optional: weather location for haiku grounding (defaults to Ballard, Seattle)
WEATHER_LOCATION_LAT=47.6762
WEATHER_LOCATION_LON=-122.3851

# Optional: override the default haiku prompt template
HAIKU_PROMPT_FILE=/path/to/custom_prompt.txt

# Optional: Temporal connection (defaults to localhost:7233)
TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_API_KEY=your-temporal-api-key

# Optional: override the target repo at the CLI level
GIT_REPOSITORY_URL=https://github.com/username/target-repo.git
```

## Architecture at a glance

- **CLI entry**: `around_the_grounds/main.py` — `--site`, `--preview`, `--deploy`, `--config`
- **Site loader**: `around_the_grounds/config/loader.py` — reads `config/sites/*.json` into `SiteConfig`
- **Parsers**: `parsers/generic/` (config-driven, four platforms) and `parsers/<venue>.py` (hand-written, registered in `parsers/registry.py`)
- **Scraper coordinator**: `scrapers/coordinator.py` — async, concurrent, error-isolated
- **Web data + deploy**: `main.py:generate_web_data` and `main.py:_deploy_with_github_auth` — the single source of truth for both CLI and Temporal paths
- **Temporal**: `temporal/workflows.py` (workflow), `temporal/activities.py` (activities), `temporal/worker.py` (worker process). The workflow resolves a `site_key`, calls a `load_site` activity to fetch `SiteConfig`, scrapes per-venue in parallel batches, and delegates `generate_web_data` and `deploy_to_git` to the same `main.py` functions the CLI uses
- **Templates**: `public_templates/<template>/` — one directory per template, copied verbatim into the target repo at deploy time
- **Tests**: 490 tests (`uv run python -m pytest`) covering parsers, generic platforms, scraper coordinator, AI utilities, weather, multi-site deploy strategies, and Temporal activity contracts

For the full architecture rundown including the deploy strategy decision tree, the AI subsystems, and the testing strategy, see [CLAUDE.md](./CLAUDE.md).

## Documentation

| File | Topic |
|---|---|
| [CLAUDE.md](./CLAUDE.md) | Full architecture, component layout, dev workflow |
| [ADDING-VENUES.md](./ADDING-VENUES.md) | Generic-vs-venue-specific parser decision tree, per-platform config fields |
| [DEPLOYMENT.MD](./DEPLOYMENT.MD) | GitHub App setup and deploy strategy details |
| [WEB-DEPLOYMENT.md](./WEB-DEPLOYMENT.md) | End-to-end deployment walkthrough and troubleshooting |
| [SCHEDULES.md](./SCHEDULES.md) | Temporal schedule management commands |
| [HAIKU-GENERATOR.md](./HAIKU-GENERATOR.md) | Haiku generator configuration and prompt customization |
| [VISION-ANALYSIS.md](./VISION-ANALYSIS.md) | Claude Vision integration for vendor identification |
| [ERROR-HANDLING.md](./ERROR-HANDLING.md) | Error isolation and retry behavior |
| [TESTING.md](./TESTING.md) | Test layout and how to run subsets |
| [TYPE-ANNOTATIONS.md](./TYPE-ANNOTATIONS.md) | MyPy strict-mode contract and conventions |

## Development

```bash
uv sync --dev                          # Install dev dependencies
uv run python -m pytest                # Full test suite (490 tests)
uv run black .                         # Format
uv run flake8                          # Lint
uv run mypy around_the_grounds/        # Type check
```

## Requirements

- Python 3.8+
- `aiohttp`, `beautifulsoup4`, `temporalio`, `anthropic` (optional, for AI features)

## License

MIT License
