# Around the Grounds 🍺🚚

A Python CLI tool for tracking food truck schedules across multiple breweries. Scrapes brewery websites asynchronously and generates a unified 7-day schedule.

## How It Works

This repository contains the **scraping and scheduling engine**. When run with `--deploy`, it:

1. **Scrapes** brewery websites for food truck schedules
2. **Copies** web templates from `public_template/` to target repository
3. **Generates** static site data (`data.json`) in target repository
4. **Target repo** is automatically deployed by platforms like Vercel

**Two-Repository Architecture:**
- **Source repo** (this one): Contains scraping code, runs workers, web templates
- **Target repo** (e.g., `ballard-food-trucks`): Receives complete website, served as static site

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
uv run around-the-grounds --preview    # Generate local preview files
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

This will copy web templates and generate fresh data in your target repository, triggering automatic deployment.

## Local Preview & Testing

Before deploying, you can preview changes locally:

```bash
# Generate web files locally for testing
uv run around-the-grounds --preview

# Serve locally and view in browser
cd public && python -m http.server 8000
# Visit: http://localhost:8000

# Or automated testing (server runs for 10 seconds)
cd public && (timeout 10 python -m http.server 8000 &) && sleep 2 && curl -s http://localhost:8000/
```

**What `--preview` does:**
1. Scrapes fresh data from all brewery websites
2. Copies templates from `public_template/` to `public/`
3. Generates `data.json` with current food truck data
4. Creates complete website in `public/` directory (git-ignored)

This allows you to test web interface changes, verify data accuracy, and debug issues before deploying to production.

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

### Production Deployment via CI/CD

For automated production updates using Docker and Watchtower:

A **Temporal Worker** runs in a Docker container and continuously listens for scheduled workflow executions. This worker will automatically pick up and execute any schedules you've configured (see [Scheduled Updates](#scheduled-updates) section above for creating schedules).

**Example CICD Flow:**
1. **Code changes** → GitHub Actions → Docker Hub (4 minutes)
2. **Watchtower** detects new image → pulls and restarts worker container (every 5 minutes)
3. **Temporal Worker** in container listens for scheduled workflow executions
4. **Schedules trigger** automatically (every 30 minutes, etc.) or manually starting workflows via UI/CLI/API
5. **Worker executes** scraping and deployment workflow which pushes to the target repository
6. **Data deploys** automatically to target repository → live website updates (Vercel, Netlify, etc.)

The containerized worker provides reliable, continuous execution of scheduled food truck data updates without manual intervention.

In my case it looks like this:
```bash
# 1. GitHub Actions builds and pushes to Docker Hub (takes ~4 minutes)
# 2. Watchtower runs every 5 minutes on my home server to pull the latest Temporal worker image
# 3. Monitor worker container (it should auto-restart with the new image):
ssh admin@192.168.0.20
docker ps -a -f "ancestor=steveandroulakis/around-the-grounds-worker:latest"
docker logs -f around-the-grounds-worker

# 4. Trigger Temporal schedules manually via:
#    - Temporal UI (web interface)
#    - CLI: uv run python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape
#    - Temporal API (programmatic)

# 5. Worker executes the scraping workflow
# 6. Data is pushed to target repository (e.g., github.com/steveandroulakis/ballard-food-trucks)
# 7. Target repository is deployed automatically (e.g., Vercel, Netlify
```

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
- **Web Interface**: Template files in `public_template/` (copied to target repo)
- **Tests**: 196 tests covering unit, integration, and error scenarios

## Requirements

- Python 3.8+
- Dependencies: `aiohttp`, `beautifulsoup4`, `temporalio`, `anthropic` (optional)

## License

MIT License