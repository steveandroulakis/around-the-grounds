# Multi-Site Event Aggregation Architecture Decisions

## Overview
This document captures the architectural decisions for transforming "Ground Events" from a single brewery food truck tracker into a multi-site event aggregation platform.

## Current State Analysis (Completed)

### Current Architecture
- **Single Domain Focus**: Food truck events at breweries only
- **Hard-coded Models**: `FoodTruckEvent` and `Brewery` are brewery-specific
- **Monolithic Configuration**: Single `breweries.json` file
- **Single Website Output**: One web interface for all brewery data
- **Parser Registry**: Extensible but brewery-focused

### Current Key Components
1. **Configuration**: `config/breweries.json` with brewery-specific fields
2. **Models**: `Brewery` and `FoodTruckEvent` data classes
3. **Parsers**: Extensible parser system with `BaseParser` + specific implementations
4. **Scraper**: `ScraperCoordinator` for concurrent data collection
5. **Web System**: Single `public_template/` → single website deployment
6. **Temporal**: Workflow orchestration for scheduled updates

### Extension Points Identified
- Parser registry supports new parser types
- Configuration is JSON-based and flexible
- Web deployment system uses templates
- Models use dataclasses (easily extensible)

## Target Architecture: Multi-Site Event Aggregation

### Core Principle
**Each YAML file = One unique website** with its own URL sources and deployment target.

### 1. Site-Specific Configuration System

#### File Structure
```
config/sites/
├── ballard-food-trucks.yaml
├── fremont-breweries.yaml
├── seattle-concerts.yaml
├── capitol-hill-kids.yaml
└── georgetown-breweries.yaml
```

#### Configuration Format
```yaml
# Example: config/sites/ballard-food-trucks.yaml
site:
  name: "Food Trucks in Ballard"
  template_type: "food_events"  # References template in templates/food_events/
  website_title: "Food Trucks in Ballard"
  repository_url: "https://github.com/user/ballard-food-trucks"
  description: "Daily food truck schedules at Ballard breweries"

sources:
  - key: "stoup-ballard"
    name: "Stoup Brewing - Ballard"
    url: "https://www.stoupbrewing.com/ballard/"
    parser_type: "stoup_brewery"
  - key: "urban-family"
    name: "Urban Family Brewing"
    url: "https://app.hivey.io/urbanfamily/public-calendar"
    parser_type: "hivey_calendar"
```

#### Key Configuration Features
- **template_type**: References shared template (multiple sites can use same template)
- **repository_url**: Each site deploys to its own repository
- **sources**: List of URLs and their parser types
- **Flexibility**: Any parser can be used by any site

### 2. Template Type System

#### Template Structure
```
templates/
├── food_events/           # Used by multiple food truck sites
│   ├── index.html
│   ├── styles.css
│   └── config.json        # Template-specific settings
├── music_events/          # Used by concert venue sites
│   ├── index.html
│   ├── styles.css
│   └── config.json
├── family_events/         # Used by kids/family event sites
│   ├── index.html
│   ├── styles.css
│   └── config.json
└── community_events/      # Used by neighborhood/community sites
    ├── index.html
    ├── styles.css
    └── config.json
```

#### Template Reuse Strategy
- Multiple sites can share template types
- Example: 5 different food truck sites all use `food_events` template
- Each site still gets its own unique website and repository
- Templates provide consistent UX across similar event categories

### 3. Generalized Data Models

#### New Models
```python
@dataclass
class EventSource:  # Replaces Brewery
    key: str
    name: str
    url: str
    parser_type: str  # References parser in registry
    parser_config: Optional[Dict[str, Any]] = None

@dataclass
class Event:  # Replaces FoodTruckEvent
    source_key: str
    source_name: str
    event_name: str
    date: datetime
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    description: Optional[str] = None
    event_category: str = "food"  # "food", "music", "family", "community"
    ai_generated_name: bool = False

@dataclass
class SiteConfig:  # New model for site configuration
    name: str
    template_type: str
    website_title: str
    repository_url: str
    description: str
    sources: List[EventSource]
```

#### Migration Strategy
- `Brewery` → `EventSource` (more generic naming)
- `FoodTruckEvent` → `Event` (supports any event type)
- Add `SiteConfig` for site-level configuration
- Maintain backwards compatibility during transition

### 4. Enhanced CLI Interface

#### Site-Specific Commands
```bash
# Run specific site configurations
uv run ground-events --site ballard-food-trucks --deploy
uv run ground-events --site seattle-concerts --preview
uv run ground-events --site capitol-hill-kids --verbose

# Run all sites (deploys to multiple repositories)
uv run ground-events --all-sites --deploy

# List available sites
uv run ground-events --list-sites

# Backwards compatibility (uses ballard-food-trucks.yaml by default)
uv run ground-events --deploy  # Still works
```

#### CLI Features
- **--site**: Specify which YAML configuration to use
- **--all-sites**: Process all YAML files in config/sites/
- **--list-sites**: Show available site configurations
- **Backwards compatibility**: Default to existing behavior if no --site specified

### 5. Technology-Based Parser System

#### Current Parser Technologies (Existing)
Based on analysis of existing parsers, they are already organized by **technology/platform**:

1. **Squarespace Calendar API** (`BaleBreakerParser`) - Squarespace calendar integration
2. **Hivey API** (`UrbanFamilyParser`) - Hivey calendar platform API
3. **Google Sheets CSV** (`ChucksGreenwoodParser`) - Google Sheets CSV export
4. **Seattle Food Truck API** (`SalehsCornerParser`) - Specialized JSON API
5. **Custom HTML Selectors** (`StoupBallardParser`) - CSS selector-based scraping
6. **Regex Text Parsing** (`ObecBrewingParser`) - Pattern-based text extraction
7. **Text Search HTML** (`WheeliePopParser`) - Simple text search in HTML

#### Enhanced Technology-Based Parser Registry
```python
class ParserRegistry:
    _parsers: Dict[str, Type[BaseParser]] = {
        # Existing technology-based parsers
        "squarespace_calendar": BaleBreakerParser,
        "hivey_api": UrbanFamilyParser,
        "google_sheets_csv": ChucksGreenwoodParser,
        "seattle_food_truck_api": SalehsCornerParser,
        "html_selectors": StoupBallardParser,
        "regex_text": ObecBrewingParser,
        "text_search_html": WheeliePopParser,

        # New technology parsers
        "ical_calendar": ICalendarParser,
        "json_api": JsonApiParser,
        "wordpress_events": WordPressEventsParser,
        "eventbrite_api": EventbriteApiParser,
        "facebook_events": FacebookEventsParser,
        "wix_calendar": WixCalendarParser,
        "drupal_events": DrupalEventsParser,
        "shopify_events": ShopifyEventsParser,
        "generic_rss": RSSFeedParser,
        "generic_xml": XMLParser,
        "csv_file": CSVFileParser,
    }
```

#### Technology-Based Parser Organization
```
parsers/
├── api_based/                    # API-driven parsers
│   ├── squarespace_calendar.py   # Squarespace Calendar API
│   ├── hivey_api.py              # Hivey calendar platform
│   ├── seattle_food_truck_api.py # Seattle Food Truck API
│   ├── eventbrite_api.py         # Eventbrite API
│   ├── facebook_events.py        # Facebook Events API
│   ├── ical_calendar.py          # iCal/ICS format
│   └── json_api.py               # Generic JSON API
├── document_based/               # Document format parsers
│   ├── google_sheets_csv.py      # Google Sheets CSV export
│   ├── csv_file.py               # Generic CSV files
│   ├── rss_feed.py               # RSS/Atom feeds
│   └── xml_parser.py             # Generic XML formats
├── html_based/                   # HTML scraping parsers
│   ├── html_selectors.py         # CSS selector-based
│   ├── regex_text.py             # Regex pattern matching
│   ├── text_search_html.py       # Simple text search
│   ├── wordpress_events.py       # WordPress event plugins
│   ├── wix_calendar.py           # Wix website calendars
│   └── drupal_events.py          # Drupal event modules
└── cms_based/                    # CMS-specific parsers
    ├── wordpress_events.py
    ├── drupal_events.py
    ├── shopify_events.py
    └── squarespace_calendar.py
```

#### Parser Library Strategy

**For New Sites (Auto-Detection)**:
When adding a new site without knowing its technology, the system can attempt parsers in order:

```python
# Automatic parser detection for new sites
auto_detection_order = [
    # 1. Try known API patterns first (most reliable)
    "ical_calendar",           # Look for .ics links
    "json_api",                # Look for JSON endpoints
    "eventbrite_api",          # Check for Eventbrite widgets
    "facebook_events",         # Check for Facebook event embeds

    # 2. Try CMS detection
    "wordpress_events",        # WordPress event plugin patterns
    "squarespace_calendar",    # Squarespace calendar signatures
    "wix_calendar",            # Wix calendar patterns
    "drupal_events",           # Drupal event module patterns

    # 3. Try document formats
    "google_sheets_csv",       # Google Sheets export links
    "csv_file",                # Direct CSV file links
    "generic_rss",             # RSS/Atom feed links

    # 4. Fall back to HTML parsing
    "html_selectors",          # Common event HTML patterns
    "regex_text",              # Text pattern matching
    "text_search_html",        # Simple text extraction
]
```

**Parser Library Features**:
- **Success Scoring**: Track which parsers work for which sites
- **Technology Fingerprinting**: Detect CMS/platform signatures
- **Configuration Templates**: Pre-built configs for common platforms
- **Learning System**: Improve detection based on success rates

**Usage Example**:
```bash
# Try auto-detection for a new site
uv run ground-events --auto-detect "https://newsite.com/events"

# Output suggests parser and generates config:
# ✅ Detected: WordPress Events plugin
# 🔧 Suggested parser: wordpress_events
# 📝 Generated config: newsite-events.yaml
```

### 6. Complete Project Structure

```
around_the_grounds/
├── config/
│   └── sites/                    # Site-specific configurations
│       ├── ballard-food-trucks.yaml
│       ├── fremont-breweries.yaml
│       ├── seattle-concerts.yaml
│       ├── capitol-hill-kids.yaml
│       └── georgetown-breweries.yaml
├── templates/                    # Template types (shared across sites)
│   ├── food_events/
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── config.json
│   ├── music_events/
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── config.json
│   ├── family_events/
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── config.json
│   └── community_events/
│       ├── index.html
│       ├── styles.css
│       └── config.json
├── models/
│   ├── event_source.py          # Generalized EventSource
│   ├── event.py                 # Generalized Event
│   ├── site_config.py           # SiteConfig model
│   ├── brewery.py               # Legacy (for backwards compatibility)
│   └── schedule.py              # Legacy (for backwards compatibility)
├── parsers/
│   ├── food/                    # Food truck parsers
│   ├── music/                   # Music venue parsers
│   ├── family/                  # Family event parsers
│   ├── generic/                 # Generic parsers
│   ├── base.py                  # Base parser (unchanged)
│   └── registry.py              # Enhanced registry
├── scrapers/
│   └── coordinator.py           # Enhanced for multi-site support
├── utils/                       # Existing utilities (unchanged)
├── temporal/                    # Enhanced for multi-site workflows
└── generated_sites/             # Local preview (git-ignored)
    ├── ballard-food-trucks/
    ├── seattle-concerts/
    └── capitol-hill-kids/
```

## Key Architectural Benefits

### 1. Infinite Scalability
- Each YAML file creates a unique website
- No limit to number of sites that can be created
- Sites are completely independent

### 2. Template Reuse
- Multiple sites can share template types
- Example: 5 different food truck sites using `food_events` template
- Consistent UX across similar event categories
- Easy to create new template types

### 3. Complete Isolation
- Each site has its own URL sources
- Each site deploys to its own repository
- Sites can't interfere with each other
- Independent update schedules possible

### 4. Flexible Parsing
- Any parser can be used by any site
- Mix and match parsers within a single site
- Easy to add new parsers for new data sources
- Generic parsers for common formats

### 5. Backwards Compatibility
- Existing brewery configuration becomes `ballard-food-trucks.yaml`
- Existing CLI commands continue to work
- Gradual migration path available

## Example Usage Scenarios

### Scenario 1: Multiple Food Truck Sites
```yaml
# ballard-food-trucks.yaml - uses food_events template
# fremont-breweries.yaml - uses food_events template
# georgetown-breweries.yaml - uses food_events template
```
Result: 3 different websites, same template type, different URL sources and repositories

### Scenario 2: Mixed Event Types
```yaml
# seattle-concerts.yaml - uses music_events template
# capitol-hill-kids.yaml - uses family_events template
# belltown-community.yaml - uses community_events template
```
Result: 3 different websites, different template types, covering different event categories

### Scenario 3: Neighborhood-Specific Aggregation
```yaml
# capitol-hill-all-events.yaml - uses community_events template
# Sources: music venues + family events + community boards in Capitol Hill
```
Result: Single website aggregating multiple event types from one geographic area

## Implementation Phases

### Phase 1: Core Infrastructure
1. Create new generalized models (`EventSource`, `Event`, `SiteConfig`)
2. Enhance CLI to support `--site` parameter
3. Create site configuration loader
4. Maintain backwards compatibility

### Phase 2: Template System
1. Move existing `public_template/` to `templates/food_events/`
2. Create template type resolution system
3. Update deployment logic for template selection

### Phase 3: Parser System Enhancement
1. Reorganize parsers into categories
2. Enhance parser registry for new parser types
3. Create generic parsers for common formats

### Phase 4: Multi-Site Deployment
1. Update deployment logic for multiple repositories
2. Enhance Temporal workflows for multi-site support
3. Create `--all-sites` functionality

### Phase 5: New Event Types
1. Create music venue parsers and templates
2. Create family event parsers and templates
3. Create community event parsers and templates

## Migration Strategy

### Backwards Compatibility
- Keep existing models during transition
- Default to `ballard-food-trucks.yaml` if no `--site` specified
- Existing CLI commands continue to work unchanged

### Data Migration
- Convert existing `config/breweries.json` to `config/sites/ballard-food-trucks.yaml`
- Move `public_template/` to `templates/food_events/`
- Update parser keys in configuration

### Testing Strategy
- Test each phase independently
- Ensure existing functionality remains intact
- Validate new functionality with example configurations

## Future Enhancements

### Template Marketplace
- Community-contributed template types
- Template versioning and updates
- Template preview and selection tools

### Parser Marketplace
- Community-contributed parsers
- Parser testing and validation tools
- Parser documentation and examples

### Advanced Scheduling
- Site-specific update schedules
- Dependency management between sites
- Bulk operations across multiple sites

### Analytics and Monitoring
- Site-specific analytics
- Event aggregation metrics
- Performance monitoring per site

---

**Decision Date**: 2025-09-22
**Status**: Approved for Implementation
**Next Steps**: Begin Phase 1 implementation