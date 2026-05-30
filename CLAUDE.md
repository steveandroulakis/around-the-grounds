# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Around the Grounds is a multi-site event aggregator platform. Each site is defined by a JSON config file in `config/sites/` — no new parser code is needed unless the site uses an unsupported platform. This repo is jointly maintained: it produces the original ballardfoodtrucks.com (Vercel-backed, deploys to the `public/` subdir of a dedicated target repo) as well as jredding's Brooklyn music and children's-events sites (GitHub Pages–backed, deploy to the target repo root). Both setups coexist via per-site config.

> **If you're merging the multi-site merge into an existing checkout**, read [MIGRATION.md](./MIGRATION.md) first. It covers per-maintainer migration notes, recommended post-pull hygiene, and the remaining latent follow-up work (per-site haiku prompts, per-site weather location, the `extraction_method` template shim, the `scrape_single_venue` timezone gap). The earlier follow-ups for unifying the Temporal deploy path and retiring `breweries.json` are now done.

Key features:
- **Multi-site support** with independent site configs for different event domains (food trucks, music, kids events), independent target repositories, and configurable per-site deploy strategies
- **Generic parser system** with platform-based parsers (WordPress, HTML selector, AJAX/JSON API) plus venue-specific parsers
- **Web interface** with per-site templates and automatic deployment to the configured target host (GitHub Pages or Vercel-via-GitHub)
- **Async web scraping** with concurrent processing of multiple venue websites
- **AI vision analysis** using Claude Vision API to extract vendor names from food truck logos/images
- **AI haiku generation** using Claude Sonnet 4.6 with real-time weather grounding (Ballard-specific; other sites opt out via `generate_description: false`)
- **Auto-deployment** with two git strategies selected by `deploy_subdir`: fresh `git init` + force-push (repo root, used by jredding's sites) or clone + scoped add (subdirectory, used by Ballard's Vercel setup)
- **Cloud Run Jobs** with Cloud Scheduler for daily automated site updates (jredding's production setup)
- **Self-hosted Temporal worker** alternative scheduling path (Ballard production setup)
- **Comprehensive error handling** with retry logic, isolation, and graceful degradation
- **Temporal workflow integration** with cloud deployment support (local, Temporal Cloud, custom servers)
- **Extensive test suite** with 499 tests covering unit, integration, vision analysis, haiku generation, weather, and error scenarios
- **Modern Python tooling** with uv for dependency management and packaging

## Development Commands

### Environment Setup
```bash
uv sync --dev  # Install all dependencies including dev tools
```

### Running the Application
```bash
uv run around-the-grounds              # Run default site (ballard-food-trucks) (~60s)
uv run around-the-grounds --verbose    # Run with verbose logging (~60s)
uv run around-the-grounds --site park-slope-music   # Run a specific site
uv run around-the-grounds --site childrens-events   # Run another site
uv run around-the-grounds --site all                # Run all configured sites
uv run around-the-grounds --config /path/to/config.json  # Use custom config (~60s)
uv run around-the-grounds --preview    # Generate local preview files (~60s)
uv run around-the-grounds --deploy     # Run and deploy to GitHub Pages (~90s total)

# With AI features enabled (vision analysis + haiku generation)
export ANTHROPIC_API_KEY="your-api-key"
uv run around-the-grounds --verbose    # Run with AI features enabled (~60-90s)
uv run around-the-grounds --deploy     # Run with AI features and deploy to web (~90s)
```

**⏱️ Execution Times:** CLI operations typically take 60-90 seconds to scrape all venue websites concurrently. Add extra time for AI features (vision analysis, haiku generation) and git operations when using `--deploy`.

### Local Preview & Testing

Before deploying, generate and test web files locally:

```bash
# Generate web files locally for testing (~60s to scrape all sites)
uv run around-the-grounds --preview

# Serve locally and view in browser
cd public && python -m http.server 8000
# Visit: http://localhost:8000

# Automated testing methods:
# Test data.json endpoint
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | head -20 && pkill -f "python -m http.server" || true

# Test for specific event data (e.g., Sunday events)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/data.json | grep "2025-07-06" && pkill -f "python -m http.server" || true

# Test full homepage (basic connectivity)
cd public && timeout 10s python -m http.server 8000 > /dev/null 2>&1 & sleep 1 && curl -s http://localhost:8000/ > /dev/null && echo "✅ Homepage loads" && pkill -f "python -m http.server" || echo "❌ Homepage failed"

# Test JavaScript rendering (requires Node.js/puppeteer - optional)
# npm install -g puppeteer-cli
cd public && timeout 15s python -m http.server 8000 > /dev/null 2>&1 & sleep 2 && \
  node -e "
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({headless: true});
  const page = await browser.newPage();
  await page.goto('http://localhost:8000');
  await page.waitForSelector('.day-section', {timeout: 5000});
  const dayHeaders = await page.$$eval('.day-header', els => els.map(el => el.textContent));
  console.log('✅ Rendered days:', dayHeaders.slice(0,2).join(', '));
  const eventCount = await page.$$eval('.truck-item', els => els.length);
  console.log('✅ Rendered events:', eventCount);
  await browser.close();
})().catch(e => console.log('❌ JS render test failed:', e.message));
" && pkill -f "python -m http.server" || echo "❌ Install puppeteer for JS testing: npm install -g puppeteer"
```

**What `--preview` does:**
- Scrapes fresh data from all venue websites for the selected site
- Copies site-specific templates from `public_templates/<template>/` to `public/`
- Generates `data.json` with current event data
- Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.


### Web Deployment

**IMPORTANT**: Web deployment requires GitHub App authentication setup. See [DEPLOYMENT.MD](./DEPLOYMENT.MD) for configuration details.

```bash
# Deploy fresh data to GitHub Pages (full workflow)
uv run around-the-grounds --deploy

# Deploy a specific site
uv run around-the-grounds --site park-slope-music --deploy

# Deploy all sites
uv run around-the-grounds --site all --deploy

# Deploy to custom repository (overrides site config target_repo)
uv run around-the-grounds --deploy --git-repo https://github.com/username/repo.git

# This command will:
# 1. Scrape all venue websites for fresh event data
# 2. Copy site-specific templates from public_templates/<template>/ to target repo root
# 3. Generate web-friendly JSON data (data.json) in target repo root
# 4. Authenticate using GitHub App credentials
# 5. git init + force push complete website to target repository
# 6. GitHub Pages serves the site automatically
```

### Deployment
See [DEPLOYMENT.MD](./DEPLOYMENT.MD)

### Temporal Schedule Management
See [SCHEDULES.md](./SCHEDULES.md)

#### Schedule Features
- **Configurable intervals**: Any number of minutes (5, 30, 60, 120, etc.)
- **Multiple deployment modes**: Works with local, Temporal Cloud, and mTLS
- **Production ready**: Built-in error handling and detailed logging
- **Full lifecycle management**: Create, list, describe, pause, unpause, trigger, update, delete

### Testing
```bash
# Full test suite (499 tests)
uv run python -m pytest                    # Run all tests
uv run python -m pytest tests/unit/        # Unit tests only
uv run python -m pytest tests/parsers/     # Parser-specific tests
uv run python -m pytest tests/integration/ # Integration tests
uv run python -m pytest tests/unit/test_vision_analyzer.py  # Vision analysis tests
uv run python -m pytest tests/unit/test_haiku_generator.py  # Haiku generation tests
uv run python -m pytest tests/integration/test_vision_integration.py  # Vision integration tests
uv run python -m pytest tests/integration/test_haiku_integration.py   # Haiku integration tests
uv run python -m pytest tests/test_error_handling.py  # Error handling tests

# Test options
uv run python -m pytest -v                 # Verbose output
uv run python -m pytest --cov=around_the_grounds --cov-report=html  # Coverage
uv run python -m pytest -k "test_error"    # Run error-related tests
uv run python -m pytest -k "vision"        # Run vision-related tests
uv run python -m pytest -k "haiku"         # Run haiku-related tests
uv run python -m pytest -x                 # Stop on first failure
```

### Code Quality
```bash
uv run black .             # Format code
uv run isort .             # Sort imports
uv run flake8             # Lint code
uv run mypy around_the_grounds/  # Type checking
```

## Architecture

The project follows a modular architecture with clear separation of concerns:

```
around_the_grounds/
├── config/
│   ├── sites/                     # Per-site JSON configurations
│   │   ├── ballard-food-trucks.json   # Ballard food trucks (9 venues, deploy_subdir="public")
│   │   ├── park-slope-music.json      # Park Slope music venues (2 venues, deploy to repo root)
│   │   └── childrens-events.json      # Brooklyn children's events (2 venues, deploy to repo root)
│   ├── loader.py                  # Site config loader (load_site_config, load_all_sites)
│   ├── haiku_prompt.txt           # Weather-grounded haiku prompt template (Ballard-specific)
│   └── settings.py                # Vision analysis and other settings
├── models/
│   ├── __init__.py                # Exports Venue, Event, SiteConfig
│   ├── brewery.py                 # Venue data model (renamed from Brewery; file name retained)
│   ├── schedule.py                # Event data model (renamed from FoodTruckEvent; file name retained)
│   └── site.py                    # SiteConfig data model (includes deploy_subdir field)
├── parsers/
│   ├── __init__.py                # Parser module exports
│   ├── base.py                    # Abstract base parser with error handling
│   ├── generic/                   # Platform-based generic parsers
│   │   ├── wordpress.py           # WordPressParser (REST API)
│   │   ├── html_selector.py       # HtmlSelectorParser (CSS selectors)
│   │   ├── ajax.py                # AjaxParser (JSON API endpoints)
│   │   └── json_ld.py             # JsonLdParser (schema.org JSON-LD)
│   ├── stoup_ballard.py           # Stoup Brewing parser (venue-specific)
│   ├── bale_breaker.py            # Bale Breaker parser (venue-specific)
│   ├── obec_brewing.py            # Obec Brewing parser (venue-specific)
│   ├── urban_family.py            # Urban Family parser — WordPress Sugar Calendar primary + Hivey fallback + vision
│   ├── wheelie_pop.py             # Wheelie Pop Brewing parser (venue-specific)
│   ├── chucks_greenwood.py        # Chuck's Hop Shop Greenwood parser (Google Sheets CSV)
│   ├── salehs_corner.py           # Saleh's Corner parser (Seattle Food Truck API)
│   ├── channel_marker.py          # Channel Marker Cider parser (Google Sheets CSV)
│   ├── lucky_envelope.py          # Lucky Envelope Brewing parser (Squarespace embedded JSON)
│   └── registry.py                # Two-tier registry (venue-specific + generic)
├── scrapers/
│   └── coordinator.py             # Async scraping coordinator with error isolation
├── temporal/                      # Temporal workflow integration
│   ├── __init__.py                # Module initialization
│   ├── workflows.py               # FoodTruckWorkflow definition
│   ├── activities.py              # ScrapeActivities and DeploymentActivities
│   ├── config.py                  # Temporal client configuration system
│   ├── schedule_manager.py        # Comprehensive schedule management script
│   ├── shared.py                  # WorkflowParams and WorkflowResult data classes
│   ├── worker.py                  # Production-ready worker with error handling
│   ├── starter.py                 # CLI workflow execution client
│   └── README.md                  # Temporal-specific documentation
├── utils/
│   ├── date_utils.py              # Date/time utilities with validation
│   ├── github_auth.py             # GitHub App JWT authentication
│   ├── vision_analyzer.py         # AI vision analysis for vendor identification
│   ├── haiku_generator.py         # AI haiku generation (weather-grounded, claude-sonnet-4-6)
│   └── weather.py                 # Open-Meteo weather fetch (free, no API key)
└── main.py                        # CLI entry point with multi-site, deploy, preview

public_templates/                  # Per-site web interface templates
├── food-trucks/                   # Ballard food trucks template (with brewery-click search)
│   └── index.html
├── music/                         # Park Slope music template
│   └── index.html
└── kids/                          # Brooklyn children's events template
    └── index.html

public/                            # Generated files (git-ignored)
├── data.json                      # Generated web data
└── index.html                     # Copied from the active template

tests/                             # Comprehensive test suite (499 tests)
├── conftest.py                    # Shared test fixtures
├── fixtures/
│   ├── csv/                       # CSV samples (channel_marker)
│   ├── html/                      # Real HTML samples from venue websites
│   ├── json/                      # JSON API response fixtures
│   └── config/                    # Test configurations
├── unit/                          # Unit tests for individual components
├── parsers/                       # Parser-specific tests (including generic parsers)
├── integration/                   # End-to-end integration tests
├── temporal/                      # Temporal workflow tests
└── test_error_handling.py         # Comprehensive error scenario tests
```

### Key Components

- **Models**: Data classes for venues and events with validation
  - `Venue`: Represents a data source (renamed from `Brewery`), includes `source_type` for parser selection
  - `Event`: Represents a single event (renamed from `FoodTruckEvent`), includes `extraction_method`
  - `SiteConfig`: Represents a deployable site with venues, template, timezone, target repo, and `deploy_subdir` (see Deployment Strategies below)
- **Parsers**: Two-tier parser system — venue-specific parsers take precedence, then generic platform parsers
  - `BaseParser`: Abstract base with HTTP error handling, validation, and logging
  - **Generic parsers** (config-driven, no code needed for new sites):
    - `WordPressParser`: Fetches events from WordPress REST API (`source_type: "wordpress"`)
    - `HtmlSelectorParser`: Extracts events via CSS selectors (`source_type: "html"`)
    - `AjaxParser`: Fetches from JSON API endpoints (`source_type: "ajax"`)
    - `JsonLdParser`: Extracts events from schema.org JSON-LD blocks (`source_type: "json-ld"`)
  - **Venue-specific parsers** (9 for Ballard food trucks): StoupBallard, BaleBreaker, Obec, UrbanFamily, WheeliePop, ChucksGreenwood, SalehsCorner, ChannelMarker, LuckyEnvelope
- **Registry**: Two-tier lookup — by `venue.key` (specific) then by `venue.source_type` (generic)
- **Scrapers**: Async coordinator with concurrent processing, retry logic, and error isolation
- **Temporal**: Workflow orchestration for reliable execution and scheduling. The `FoodTruckWorkflow` resolves a `site_key` (default `"ballard-food-trucks"` when omitted, for back-compat with the persisted hourly schedule), calls a `load_site` activity to fetch the `SiteConfig` from `config/sites/<key>.json`, scrapes per-venue in parallel batches, and delegates `generate_web_data` and `deploy_to_git` to the same `main.py` functions the CLI uses — so both Temporal and CLI runs share one implementation
- **Config**: Per-site JSON configs in `config/sites/`, loaded by `config/loader.py`
- **Utils**: Date/time utilities, AI vision analysis, weather-grounded haiku generation, Open-Meteo weather fetch, GitHub App auth
- **Web Interface**: Per-site templates in `public_templates/<template>/` deployed to the site's configured host (GitHub Pages or Vercel-via-GitHub)
- **Web Deployment**: Two git strategies selected by `SiteConfig.deploy_subdir` — see Deployment Strategies below
- **Scheduling**: Google Cloud Run Jobs with Cloud Scheduler (jredding's sites) OR a self-hosted Temporal worker (Ballard site). Both paths read the same `SiteConfig` and call the same `main.py:_deploy_with_github_auth` for git operations
- **Tests**: 490 tests covering all scenarios including generic parsers, error handling, vision analysis, haiku generation, weather fetching, multi-site deploy configuration, and the Temporal `load_site` / `generate_web_data` / `deploy_to_git` activity contracts

## Deployment Strategies

`SiteConfig.deploy_subdir` (in `config/sites/<key>.json`) selects one of two strategies in `main.py:_deploy_with_github_auth`:

| `deploy_subdir` | Strategy | Git operations | When to use |
|---|---|---|---|
| `""` (default, omitted) | **Root mode** | `git init` fresh → copy template to repo root → `git add .` → **force-push** `HEAD:main` | Target repo is dedicated to this site and served from root by GitHub Pages. Used by `park-slope-music`, `childrens-events`. Rewrites history on every deploy. |
| `"public"` (or any non-empty string) | **Subdir mode** | `git clone` target → copy template into `repo/<subdir>/` → `git add <subdir>/` → no-op short-circuit → normal `push` `HEAD:main` | Target repo has files at root that must be preserved (e.g. a Vercel project whose build output is scoped to `public/`). Used by `ballard-food-trucks`. Preserves history. |

**Ballard-specific:** `config/sites/ballard-food-trucks.json` has `deploy_subdir: "public"` and `target_repo: "https://github.com/steveandroulakis/ballard-food-trucks.git"`. A Vercel project watches that repo's `public/` folder and redeploys on every push. The merge must preserve this behavior — changing `deploy_subdir` to `""` would destroy the target repo's structure on first deploy.

### `skip_unchanged_deploys` (per-site no-op skip)

`SiteConfig.skip_unchanged_deploys` (default `false`) makes a deploy a no-op when the new `events` array matches what is already deployed. The deploy carries the prior `data.json`'s volatile fields (`updated`, `haiku`) forward so the file stays byte-identical and the staged-diff short-circuit skips the commit/push. A real change to events — or to the template/CSS — still deploys.

| Flag | Effect on deploy |
|---|---|
| `false` (default) | Every run deploys. `data.json` always differs because `updated` is regenerated (and, for sites that opt in, the haiku). Used by `ballard-food-trucks` so its **hourly weather haiku deploys every run** — see Haiku Generator below. |
| `true` | No-op runs (events unchanged) skip the commit/push entirely. Used by `park-slope-music`, `childrens-events`. |

**Root-mode interaction:** because the skip needs the prior `data.json` to diff against, enabling `skip_unchanged_deploys` on a **root-mode** site forces a `git clone` (with a fresh-`init` fallback for empty/new target repos) instead of the plain `git init`. Such sites therefore push **normally** (`git push HEAD:main`) and **accumulate history** rather than force-pushing a rewritten single commit each run. The `cloned ? normal-push : force-push` invariant in `_deploy_with_github_auth` keeps plain root mode (flag off) on the original force-push path.

**Do not set `skip_unchanged_deploys: true` together with `generate_description: true`** unless you want the haiku frozen until the event set changes — the carry-forward would freeze it. Ballard deliberately keeps the flag off for this reason.

### Core Dependencies

**Production:**
- `aiohttp` - Async HTTP client for web scraping with timeout handling
- `beautifulsoup4` - HTML parsing with error tolerance
- `lxml` - Fast XML/HTML parser backend
- `requests` - HTTP library (legacy support)
- `anthropic` - Claude API for AI-powered image analysis and haiku generation
- `temporalio` - Temporal Python SDK for workflow orchestration

**Development & Testing:**
- `pytest` - Test framework with async support
- `pytest-asyncio` - Async test support
- `aioresponses` - HTTP response mocking for tests
- `pytest-mock` - Advanced mocking capabilities
- `freezegun` - Time mocking for date-sensitive tests
- `pytest-cov` - Code coverage reporting

The CLI is configured in `pyproject.toml` with entry point `around-the-grounds = "around_the_grounds.main:main"`.

## Adding New Sites and Venues

See [ADDING-VENUES.md](./ADDING-VENUES.md) for how to add new sites and venues using JSON config files and generic parsers.

## Haiku Generator

The system includes AI-powered haiku generation (`claude-sonnet-4-6` at `temperature=0.85`) that creates contextual, poetic descriptions of daily food truck scenes. Haikus are **grounded in real-time weather data** fetched from Open-Meteo (free, no API key). The prompt incorporates time-of-day awareness, weather-driven sensory imagery, and beer/brewery references while explicitly avoiding invented sensory details.

Weather location defaults to Ballard, Seattle but is overridable via `WEATHER_LOCATION_LAT` / `WEATHER_LOCATION_LON` environment variables. Weather data is **required** — if the fetch fails, no haiku is generated (the system falls back gracefully).

Haiku generation is **per-site opt-in** via `generate_description: true/false` in the site config. Currently only `ballard-food-trucks` opts in; `park-slope-music` and `childrens-events` set it to `false`. The prompt template is also Ballard-specific (mentions Pacific Northwest, breweries) — when adding haiku to other sites, plan to override `haiku_prompt.txt` via `HAIKU_PROMPT_FILE` env var or customize per-site.

See [HAIKU-GENERATOR.md](./HAIKU-GENERATOR.md) for detailed documentation on configuration, usage, and implementation.

## AI Vision Analysis

The system includes AI-powered vision analysis to extract food truck vendor names from logos and images when text-based methods fail. The analyzer uses Claude Vision API as a fallback, with retry logic and graceful degradation.

See [VISION-ANALYSIS.md](./VISION-ANALYSIS.md) for detailed documentation on configuration, usage, and implementation.

## Error Handling Strategy

The application implements comprehensive error handling with error isolation, graceful degradation, and selective retry logic.

See [ERROR-HANDLING.md](./ERROR-HANDLING.md) for the complete error handling strategy guide.

## Code Standards

- **Line length**: 88 characters (Black formatting)
- **Type hints**: Required throughout (`mypy` with `disallow_untyped_defs = true`)
- **Python compatibility**: 3.8+ required
- **Import sorting**: Black profile via isort
- **Async patterns**: async/await for all I/O operations
- **Error handling**: Comprehensive error handling and logging required
- **Testing**: All new code must include unit tests and error scenario tests
- **Logging**: Use class loggers (`self.logger`) with appropriate levels

## Testing Strategy

The project includes a comprehensive test suite with 499 tests covering unit, integration, generic parsers, vision analysis, haiku generation, weather fetching, and error scenarios.

See [TESTING.md](./TESTING.md) for the complete testing strategy and guide.

## Development Workflow

When working on this project:

1. **Run tests first** to ensure current functionality works
2. **Write failing tests** for new features before implementation
3. **Implement with error handling** - always include try/catch and logging
4. **Test error scenarios** - network failures, invalid data, timeouts
5. **Preview changes locally** using `--preview` flag before deployment
6. **Run full test suite** before committing changes
7. **Update documentation** if adding new parsers or changing architecture

### Local Development Workflow
```bash
# 1. Make code changes
# 2. Test locally with preview
uv run around-the-grounds --preview
cd public && python -m http.server 8000

# 3. Run tests
uv run python -m pytest

# 4. Deploy when ready
uv run around-the-grounds --deploy
```

## Web Deployment Workflow

See [WEB-DEPLOYMENT.md](./WEB-DEPLOYMENT.md) for the complete web deployment workflow guide.

## Type Annotations

The project uses strict type checking with MyPy (`disallow_untyped_defs = true`) and Pylance.

See [TYPE-ANNOTATIONS.md](./TYPE-ANNOTATIONS.md) for the comprehensive type annotation maintenance guide.

## Troubleshooting Common Issues

- **Parser not found**: Check `parsers/registry.py` registration
- **Network timeouts**: Adjust timeout in `ScraperCoordinator` constructor
- **Date parsing issues**: Check `utils/date_utils.py` patterns and add new formats
- **Test failures**: Use `pytest -v -s` for detailed output and debug prints
- **Import errors**: Ensure `__init__.py` files are present and imports are correct