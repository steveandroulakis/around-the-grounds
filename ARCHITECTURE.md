# Around the Grounds — Architecture Overview

## System Summary

Around the Grounds is a **multi-site event aggregator platform** that scrapes venue websites, enriches data with AI, and deploys static sites to GitHub Pages. Each site (food trucks, music, kids events) is defined entirely by a JSON config — no code changes needed for new sites using supported platforms.

---

## High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI / Entry Point                              │
│                           around_the_grounds/main.py                        │
│                                                                             │
│   Flags: --site <key|all>  --config <path>  --preview  --deploy  --verbose  │
└──────────────┬──────────────────────┬──────────────────────┬────────────────┘
               │                      │                      │
               ▼                      ▼                      ▼
┌──────────────────────┐  ┌───────────────────┐  ┌──────────────────────────┐
│   Config Loader      │  │  Scrape Pipeline  │  │   Output / Deployment    │
│                      │  │                   │  │                          │
│  config/loader.py    │  │  Coordinator →    │  │  --preview → public/     │
│  config/sites/*.json │  │  Registry →       │  │  --deploy  → GitHub Pages│
│                      │  │  Parsers          │  │  (default) → CLI stdout  │
└──────────┬───────────┘  └─────────┬─────────┘  └────────────┬─────────────┘
           │                        │                          │
           ▼                        ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            SiteConfig (data model)                           │
│                                                                              │
│  key: "park-slope-music"    template: "music"    timezone: "America/New_York"│
│  venues: [Venue, ...]       target_repo: "..."   generate_description: false │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Pipeline

```
                    ┌──────────────────┐
                    │  Site Config JSON │
                    │  (config/sites/) │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Config Loader   │
                    │  → SiteConfig    │
                    │  → List[Venue]   │
                    └────────┬─────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │     ScraperCoordinator       │
              │  (async, max_concurrent=5)   │
              └──────┬───────────────┬───────┘
                     │               │
            ┌────────┘               └────────┐
            ▼                                 ▼
   ┌─────────────────┐              ┌─────────────────┐
   │  ParserRegistry │              │  Error Isolation │
   │                 │              │                  │
   │ 1. venue-key?   │              │ Per-venue errors │
   │    → specific   │              │ don't block      │
   │ 2. source_type? │              │ other venues     │
   │    → generic    │              └─────────┬────────┘
   └────────┬────────┘                        │
            │                                 │
    ┌───────┼───────────────┐                 │
    │       │               │                 │
    ▼       ▼               ▼                 │
┌───────┐┌───────┐┌────────────┐              │
│ HTML  ││ Ajax  ││ WordPress  │   + 7 venue  │
│Selector││Parser ││  Parser   │   specific   │
│Parser ││       ││            │   parsers    │
└───┬───┘└───┬───┘└─────┬──────┘              │
    │        │           │                    │
    └────────┼───────────┘                    │
             │                                │
             ▼                                │
    ┌──────────────────┐                      │
    │   List[Event]    │◄─────────────────────┘
    │                  │     (+ ScrapingErrors)
    │  Filtered: next  │
    │  7 days, sorted  │
    │  by date/time    │
    └────────┬─────────┘
             │
     ┌───────┼───────────────┐
     │       │               │
     ▼       ▼               ▼
┌────────┐┌──────────┐┌──────────────┐
│  CLI   ││ Preview  ││   Deploy     │
│ Output ││ public/  ││ GitHub Pages │
│ stdout ││data.json ││ (force push) │
└────────┘└──────────┘└──────────────┘
```

---

## Component Architecture

### Parser System (Two-Tier Registry)

```
                      ParserRegistry.get_parser(venue)
                                  │
                     ┌────────────┴────────────┐
                     │                         │
              Tier 1: by venue.key      Tier 2: by venue.source_type
              (venue-specific)          (generic / platform-based)
                     │                         │
         ┌───────────┼────────┐       ┌────────┼──────────┐
         │           │        │       │        │          │
    ┌─────────┐ ┌────────┐ ┌───┐  ┌──────┐ ┌──────┐ ┌─────────┐
    │  Stoup  │ │ Urban  │ │...│  │ HTML │ │ Ajax │ │WordPress│
    │ Ballard │ │ Family │ │   │  │Select│ │Parser│ │ Parser  │
    └─────────┘ └────┬───┘ └───┘  └──────┘ └──────┘ └─────────┘
                     │
                     ▼
              ┌─────────────┐
              │   Vision    │   (optional AI fallback
              │  Analyzer   │    for image extraction)
              └─────────────┘

    All parsers extend BaseParser:
    ├── async parse(session) → List[Event]
    ├── async fetch_page(session, url) → BeautifulSoup
    ├── validate_event(event) → bool
    └── filter_valid_events(events) → List[Event]
```

### AI Enrichment Layer

```
┌─────────────────────────────────────────────────────────┐
│                    AI Services Layer                     │
│                (Claude API — Sonnet model)               │
│                                                         │
│  ┌─────────────────────┐    ┌────────────────────────┐  │
│  │   Vision Analyzer   │    │   Haiku Generator      │  │
│  │                     │    │                         │  │
│  │ • Image → text      │    │ • Events → 5-7-5 haiku │  │
│  │ • Logo extraction   │    │ • Seasonal context      │  │
│  │ • Retry + backoff   │    │ • Per-site generation   │  │
│  │ • Graceful degrade  │    │ • Prompt-template driven│  │
│  │                     │    │                         │  │
│  │ Trigger: parser     │    │ Trigger: main.py when   │  │
│  │ can't extract name  │    │ generate_description=   │  │
│  │ from HTML/API       │    │ true in site config     │  │
│  └─────────────────────┘    └────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Deployment Topology

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Execution Environments                         │
│                                                                       │
│  ┌─────────────┐    ┌───────────────┐    ┌─────────────────────────┐ │
│  │  Local CLI  │    │  Cloud Run    │    │    Temporal Cloud       │ │
│  │             │    │  (Scheduled)  │    │    (Workflow Engine)    │ │
│  │ --preview   │    │               │    │                        │ │
│  │ --deploy    │    │ Cloud         │    │ FoodTruckWorkflow      │ │
│  │ --site X    │    │ Scheduler     │    │ → ScrapeActivities     │ │
│  │             │    │ (daily cron)  │    │ → DeployActivities     │ │
│  └──────┬──────┘    └───────┬───────┘    └───────────┬────────────┘ │
│         │                   │                        │               │
│         └───────────────────┼────────────────────────┘               │
│                             │                                        │
│                             ▼                                        │
│               ┌──────────────────────────┐                           │
│               │   Core Scrape Pipeline   │                           │
│               │  (same code in all envs) │                           │
│               └──────────────┬───────────┘                           │
│                              │                                       │
└──────────────────────────────┼───────────────────────────────────────┘
                               │
                               ▼
            ┌──────────────────────────────────────────────────────────┐
            │                   Target Repositories                     │
            │                                                           │
            │  steveandroulakis/ballard-food-trucks                     │
            │    → Vercel watches /public/ subdir, redeploys            │
            │    → Strategy: clone + scoped add to public/              │
            │                                                           │
            │  jredding/atg-park-slope-music                            │
            │  jredding/atg-childrens-events                            │
            │    → GitHub Pages serves repo root                        │
            │    → Strategy: fresh git init + force-push                │
            │                                                           │
            │  Per-site strategy chosen by SiteConfig.deploy_subdir     │
            └──────────────────────────────────────────────────────────┘
```

---

## Data Models

```
SiteConfig
├── key: str                    ("park-slope-music")
├── name: str                   ("Park Slope Music")
├── template: str               ("music")
├── timezone: str               ("America/New_York")
├── target_repo: str            ("https://github.com/.../atg-park-slope-music.git")
├── generate_description: bool  (false)
├── deploy_subdir: str          (""  → root deploy / force-push
│                                "public" → subdir deploy / clone+scoped add)
└── venues: List[Venue]
       ├── key: str             ("union-hall")
       ├── name: str            ("Union Hall")
       ├── url: str             ("https://...")
       ├── source_type: str     ("html" | "ajax" | "wordpress" | "json-ld")
       └── parser_config: Dict  (CSS selectors, API paths, field maps)

Event
├── venue_key: str              ("union-hall")
├── venue_name: str             ("Union Hall")
├── title: str                  ("Jazz Night feat. Quartet X")
├── date: datetime              (2026-02-28)
├── start_time: Optional[datetime]
├── end_time: Optional[datetime]
├── description: Optional[str]
└── extraction_method: str      ("html" | "api" | "csv" | "ai-vision" | "json-ld")
```

---

## Web Template System

```
public_templates/
├── food-trucks/          ← Ballard food trucks
│   └── index.html           (Space Mono font, minimal)
├── music/                ← Park Slope music
│   └── index.html           (themed for music events)
└── kids/                 ← Brooklyn children's events
    └── index.html           (family-friendly design)

Template contract:
  • Fetches data.json at load time
  • Renders events grouped by day
  • Displays timezone in header
  • Shows haiku/description if present
  • Responsive single-page design
```

---

## External Dependencies Map

```
┌─────────────────────────────────────────────────┐
│              Around the Grounds                  │
│                                                  │
│   ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│   │ aiohttp  │  │  bs4 +   │  │  anthropic   │ │
│   │ (async   │  │  lxml    │  │  (Claude API │ │
│   │  HTTP)   │  │ (parsing)│  │  vision +    │ │
│   │          │  │          │  │  text gen)   │ │
│   └─────┬────┘  └────┬─────┘  └──────┬───────┘ │
│         │             │               │          │
└─────────┼─────────────┼───────────────┼──────────┘
          │             │               │
          ▼             ▼               ▼
   ┌────────────┐  ┌────────┐   ┌────────────────┐
   │   Venue    │  │  HTML  │   │  Anthropic API │
   │  Websites  │  │ from   │   │  (Claude       │
   │  (7+ URLs) │  │ venues │   │   Sonnet)      │
   └────────────┘  └────────┘   └────────────────┘

   ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐
   │  GitHub API │  │ Temporal     │  │  Google Cloud    │
   │  (App Auth) │  │ Cloud (opt.) │  │  Run (opt.)      │
   │  (Pages     │  │ (workflow    │  │  (scheduled      │
   │   deploy)   │  │  orchestr.)  │  │   execution)     │
   └─────────────┘  └──────────────┘  └─────────────────┘
```

---

## Configuration-Driven Extensibility

Adding a **new site** requires **zero code changes** if the venues use supported platforms:

```
1. Create config/sites/my-new-site.json
   {
     "key": "my-new-site",
     "name": "My New Site",
     "template": "music",            ← reuse existing or create new
     "timezone": "America/New_York",
     "target_repo": "https://github.com/.../my-repo.git",
     "venues": [
       {
         "key": "venue-a",
         "name": "Venue A",
         "url": "https://venue-a.com",
         "source_type": "html",       ← html | ajax | wordpress
         "parser_config": { ... }     ← CSS selectors / API config
       }
     ]
   }

2. Run: uv run around-the-grounds --site my-new-site --preview

   That's it. The generic parser handles the rest.
```

Adding a **new parser platform** requires:
1. New parser class extending `BaseParser` in `parsers/generic/`
2. Register in `ParserRegistry` under a new `source_type`

---

## Current Sites

| Site Key              | Template     | Timezone            | Venues | Parser Types Used     | Deploy strategy                       | Target repo                                     |
|-----------------------|--------------|---------------------|--------|-----------------------|---------------------------------------|-------------------------------------------------|
| ballard-food-trucks   | food-trucks  | America/Los_Angeles | 9      | 9 venue-specific      | Clone + scoped add to `public/`       | `steveandroulakis/ballard-food-trucks`          |
| park-slope-music      | music        | America/New_York    | 4      | html, ajax, json-ld   | Fresh init + force-push to root       | `jredding/atg-park-slope-music`                 |
| childrens-events      | kids         | America/New_York    | 2      | ajax, wordpress       | Fresh init + force-push to root       | `jredding/atg-childrens-events`                 |

---

## Key Architectural Patterns

| Pattern                    | Where                         | Purpose                                          |
|----------------------------|-------------------------------|--------------------------------------------------|
| Two-tier parser registry   | parsers/registry.py           | Venue-specific override → generic fallback        |
| Async concurrency          | scrapers/coordinator.py       | Parallel venue scraping with bounded concurrency  |
| Error isolation            | scrapers/coordinator.py       | One venue failure doesn't block others            |
| Exponential backoff retry  | coordinator + AI utils        | Transient failure recovery                        |
| Config-driven parsing      | config/sites/*.json           | New sites without code changes                    |
| Graceful AI degradation    | vision_analyzer, haiku_gen    | AI features optional; system works without them   |
| Template-per-site          | public_templates/             | Independent UI per domain                         |
| Per-site deploy strategy   | main.py _deploy_with_github_auth | Force-push root (GH Pages) OR clone+scoped subdir (Vercel), selected by `SiteConfig.deploy_subdir` |
| Site-level timezone        | SiteConfig.timezone           | Correct filtering/display across regions          |
| Weather-grounded AI        | utils/haiku_generator.py + weather.py | Haiku prompts use real-time weather; required when `generate_description: true` |

---

## Expansion Surface Areas

These are the natural extension points for new feature sets:

1. **New parser platforms** — Add to `parsers/generic/` (e.g., Eventbrite API, iCal feed, RSS)
2. **New site templates** — Add to `public_templates/` (theme per event domain)
3. **New AI enrichments** — Add to `utils/` (categorization, recommendations, summaries)
4. **New output targets** — Beyond GitHub Pages (S3, Netlify, email digest, RSS feed)
5. **New data models** — Extend Event/Venue with pricing, location/geo, categories, images
6. **Real-time features** — WebSocket/SSE for live updates vs. static deploy
7. **User-facing API** — REST/GraphQL layer over scraped data
8. **Notification system** — Alerts for new events matching user preferences
9. **Multi-region support** — Already multi-timezone; extend with i18n/l10n
10. **Analytics/monitoring** — Scraping success rates, event coverage, deploy health
