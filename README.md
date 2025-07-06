# Around the Grounds 🍺🚚

A Python CLI tool for tracking food truck schedules across multiple breweries. Scrapes brewery websites asynchronously and generates a unified 7-day schedule.

## How It Works

This repository contains the **scraping and scheduling engine**. When run with `--deploy`, it:

1. **Scrapes** brewery websites for food truck schedules
2. **Generates** static site data (`data.json`) 
3. **Pushes** data to a separate **target repository**
4. **Target repo** is automatically deployed by platforms like Vercel

**Two-Repository Architecture:**
- **Source repo** (this one): Contains scraping code, runs workers
- **Target repo** (e.g., `ballard-food-trucks`): Receives data, served as website

## Quick Start

### Installation
```bash
git clone https://github.com/steveandroulakis/around-the-grounds
cd around-the-grounds
uv sync
```

### Basic CLI Usage
```bash
uv run around-the-grounds              # Show 7-day schedule
uv run around-the-grounds --verbose    # With detailed logging
```

### Example Output
```
🍺 Around the Grounds - Food Truck Tracker
==================================================
Found 23 food truck events:

📅 Saturday, July 05, 2025
  🚚 Woodshop BBQ @ Stoup Brewing - Ballard 01:00 PM - 08:00 PM
  🚚 Kaosamai Thai @ Obec Brewing 04:00 PM - 08:00 PM

📅 Sunday, July 06, 2025  
  🚚 Burger Planet @ Stoup Brewing - Ballard 01:00 PM - 07:00 PM
  🚚 TOLU 🖼️🤖 @ Urban Family Brewing 01:00 PM - 07:00 PM
```

## Web Deployment (Optional)

To deploy a live website, you need a **target repository** and **GitHub App** for authentication.

### Prerequisites
- Target GitHub repository (e.g., `username/ballard-food-trucks`)  
- GitHub App with repository access
- Deployment platform (Vercel, Netlify, etc.)

### GitHub App Setup

1. **Create GitHub App** at https://github.com/settings/apps
   - **Repository permissions**: Contents (Read & Write), Metadata (Read)
   - **Generate private key** and save the `.pem` file
   - **Install app** on your target repository

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your GitHub App credentials:
   # GITHUB_APP_ID=123456
   # GITHUB_APP_INSTALLATION_ID=12345678  
   # GITHUB_APP_PRIVATE_KEY_B64=<base64-encoded-private-key>
   # GIT_REPOSITORY_URL=https://github.com/username/ballard-food-trucks.git
   ```

3. **Deploy Data**
   ```bash
   uv run around-the-grounds --deploy
   ```

This will scrape fresh data and push it to your target repository, triggering automatic deployment.

## Scheduled Updates

Use **Temporal workflows** to run automatic updates with a persistent worker system.

### Setup Temporal Worker
```bash
# Start worker (runs continuously)
uv run python -m around_the_grounds.temporal.worker

# Create schedule (runs every 30 minutes) 
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30
```

### Schedule Management
```bash
# List all schedules
uv run python -m around_the_grounds.temporal.schedule_manager list

# Pause/unpause schedules
uv run python -m around_the_grounds.temporal.schedule_manager pause --schedule-id daily-scrape
uv run python -m around_the_grounds.temporal.schedule_manager unpause --schedule-id daily-scrape

# Trigger immediate execution
uv run python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape

# Delete schedule
uv run python -m around_the_grounds.temporal.schedule_manager delete --schedule-id daily-scrape
```

Workers can run on any system (local, cloud, Synology NAS) and will receive scheduled workflow executions from Temporal.

## Configuration

### Supported Breweries
- **Stoup Brewing - Ballard**: HTML parsing with date/time extraction
- **Yonder Cider & Bale Breaker - Ballard**: Squarespace API integration  
- **Obec Brewing**: Text-based parsing
- **Urban Family Brewing**: Hivey API with AI vision analysis fallback

### Environment Variables
```bash
# Optional: AI vision analysis for vendor name extraction
ANTHROPIC_API_KEY=your-anthropic-api-key

# Required for web deployment
GITHUB_APP_ID=123456
GITHUB_APP_INSTALLATION_ID=12345678
GITHUB_APP_PRIVATE_KEY_B64=base64-encoded-private-key
GIT_REPOSITORY_URL=https://github.com/username/target-repo.git

# Optional: Temporal configuration (defaults to localhost)
TEMPORAL_ADDRESS=your-namespace.acct.tmprl.cloud:7233
TEMPORAL_API_KEY=your-temporal-api-key
```

### Custom Repository
```bash
# Deploy to specific repository
uv run around-the-grounds --deploy --git-repo https://github.com/username/custom-repo.git

# Or set environment variable
export GIT_REPOSITORY_URL="https://github.com/username/custom-repo.git"
uv run around-the-grounds --deploy
```

## Development

### Setup
```bash
uv sync --dev                          # Install dev dependencies
```

### Testing  
```bash
uv run python -m pytest                # Run all 196 tests
uv run python -m pytest -v             # Verbose output
uv run python -m pytest tests/parsers/ # Parser-specific tests
```

### Code Quality
```bash
uv run black .                         # Format code
uv run flake8                          # Lint code  
uv run mypy around_the_grounds/        # Type checking
```

### Adding New Breweries
1. Create parser class in `around_the_grounds/parsers/`
2. Register parser in `around_the_grounds/parsers/registry.py`
3. Add brewery config to `around_the_grounds/config/breweries.json`
4. Write tests in `tests/parsers/`

See [CLAUDE.md](CLAUDE.md) for detailed development documentation.

## Architecture

- **CLI Tool**: `around_the_grounds/main.py` - Entry point
- **Parsers**: Extensible system for different brewery websites
- **Scrapers**: Async coordinator with error handling and retries
- **Temporal**: Workflow orchestration for reliable scheduling  
- **Web Interface**: Static files in `public/` (deployed to target repo)
- **Tests**: 196 tests covering unit, integration, and error scenarios

## Requirements

- Python 3.8+
- Dependencies: `aiohttp`, `beautifulsoup4`, `temporalio`, `anthropic` (optional)

## License

MIT License