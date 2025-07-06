# Temporal Workflow Integration

This directory contains the Temporal workflow integration for Around the Grounds food truck tracking system. The integration provides reliable, observable, and schedulable execution of the complete scraping and deployment pipeline.

## Overview

The Temporal integration wraps existing functionality in workflows and activities to provide:
- **Reliable execution** with automatic retries and error handling
- **Observability** through Temporal UI and structured logging
- **Scheduling** support for automated runs
- **Zero code duplication** by wrapping existing CLI functionality
- **Production-ready** worker with proper resource management

## Architecture

```
temporal/
├── __init__.py        # Module initialization
├── activities.py      # ScrapeActivities and DeploymentActivities  
├── shared.py          # WorkflowParams and WorkflowResult data classes
├── starter.py         # CLI workflow execution client
├── workflows.py       # FoodTruckWorkflow definition
├── worker.py          # Production-ready worker process
└── README.md          # This documentation
```

### Core Components

- **FoodTruckWorkflow**: Main workflow that orchestrates the complete pipeline
- **ScrapeActivities**: Activities wrapping brewery configuration and scraping functionality
- **DeploymentActivities**: Activities for web data generation and git operations
- **FoodTruckWorker**: Production worker with thread pools and signal handling
- **FoodTruckStarter**: CLI client for manual workflow execution

## Quick Start

### Prerequisites

1. **Temporal Server**: Ensure Temporal server is running locally on `localhost:7233`
2. **Dependencies**: Run `uv sync` to install all dependencies including `temporalio`
3. **Environment**: Set up any required environment variables (e.g., `ANTHROPIC_API_KEY`)

### Basic Usage

1. **Start Worker** (in terminal 1):
```bash
uv run python -m around_the_grounds.temporal.worker
```

2. **Execute Workflow** (in terminal 2):
```bash
# Basic execution (scraping only)
uv run python -m around_the_grounds.temporal.starter

# With deployment
uv run python -m around_the_grounds.temporal.starter --deploy

# With verbose logging
uv run python -m around_the_grounds.temporal.starter --deploy --verbose
```

## Worker Configuration

### Production Worker Features

The `FoodTruckWorker` class provides production-ready capabilities:

```python
# Production-ready worker with:
worker = FoodTruckWorker(temporal_address="localhost:7233")

# Features:
# - Thread pool executor (10 max workers)
# - Signal handling (SIGINT, SIGTERM)
# - Graceful shutdown
# - Enhanced logging
# - Error handling and recovery
```

### Starting the Worker

```bash
# Basic worker startup
uv run python -m around_the_grounds.temporal.worker

# Worker will output:
# ✅ Connected to Temporal at localhost:7233
# 🔧 Starting Temporal worker for food truck workflows...
# 📋 Task queue: food-truck-task-queue
# 💼 Max workers: 10
```

### Stopping the Worker

The worker handles graceful shutdown via signals:
- **Ctrl+C** (SIGINT): Graceful shutdown
- **SIGTERM**: Graceful shutdown in production environments

## Workflow Execution

### Manual Execution

```bash
# Basic execution
uv run python -m around_the_grounds.temporal.starter

# With deployment to web
uv run python -m around_the_grounds.temporal.starter --deploy

# With custom configuration
uv run python -m around_the_grounds.temporal.starter --config /path/to/config.json

# With custom workflow ID for tracking
uv run python -m around_the_grounds.temporal.starter --workflow-id daily-update-2025

# Connect to different Temporal server
uv run python -m around_the_grounds.temporal.starter --temporal-address production:7233

# Verbose logging for debugging
uv run python -m around_the_grounds.temporal.starter --verbose
```

### Workflow Parameters

The workflow accepts parameters via the `WorkflowParams` data class:

```python
@dataclass
class WorkflowParams:
    config_path: Optional[str] = None  # Path to brewery config JSON
    deploy: bool = False               # Whether to deploy to web
```

### Workflow Results

The workflow returns results via the `WorkflowResult` data class:

```python
@dataclass
class WorkflowResult:
    success: bool                      # Overall success status
    message: str                       # Human-readable result message
    events_count: Optional[int] = None # Number of events found
    errors: Optional[List[str]] = None # Any errors encountered
    deployed: bool = False             # Whether deployment succeeded
```

## Activities

### ScrapeActivities

Activities that wrap existing scraping functionality:

- `load_brewery_config(config_path)`: Load brewery configuration
- `scrape_food_trucks(brewery_configs)`: Scrape all breweries for events

### DeploymentActivities

Activities for web deployment:

- `generate_web_data(events)`: Generate web-friendly JSON from events
- `deploy_to_git(web_data)`: Deploy data to git repository

### Activity Timeouts

Activities are configured with appropriate timeouts:
- Configuration loading: 30 seconds
- Scraping: 5 minutes (handles multiple brewery sites)
- Web data generation: 30 seconds
- Git deployment: 2 minutes

## Monitoring and Observability

### Temporal UI

Visit `http://localhost:8233` to monitor workflows:
- View workflow execution history
- Monitor activity performance
- Debug failures with stack traces
- Track workflow duration and success rates

### Logging

The integration provides structured logging at multiple levels:

```bash
# INFO level (default)
2025-07-05 21:28:42,600 - __main__ - INFO - ✅ Connected to Temporal at localhost:7233
2025-07-05 21:28:42,600 - __main__ - INFO - 🚀 Starting workflow: food-truck-workflow-20250705-212842

# DEBUG level (with --verbose)
2025-07-05 21:28:42,600 - __main__ - DEBUG - Loading brewery configuration from default path
```

### Workflow IDs

Workflow IDs are automatically generated with timestamps for tracking:
- Format: `food-truck-workflow-YYYYMMDD-HHMMSS`
- Custom IDs supported via `--workflow-id` parameter
- Visible in Temporal UI for easy monitoring

## Error Handling

### Activity-Level Error Handling

Each activity includes comprehensive error handling:
- Network failures: Automatic retries with exponential backoff
- Parsing errors: Graceful degradation with detailed logging
- Git operations: Fallback handling for deployment issues

### Workflow-Level Error Handling

The workflow handles activity failures gracefully:
- Individual activity failures don't stop the entire workflow
- Detailed error reporting in workflow results
- Partial success scenarios supported

### Common Error Scenarios

1. **Temporal Connection Failures**:
   ```
   ❌ Failed to connect to Temporal: [Errno 61] Connection refused
   ```
   - Solution: Ensure Temporal server is running on `localhost:7233`

2. **Activity Timeouts**:
   ```
   Activity timed out after 5 minutes
   ```
   - Solution: Check network connectivity and brewery website availability

3. **Git Deployment Failures**:
   ```
   Git push failed, but commit succeeded
   ```
   - Solution: Check git remote configuration (deployment still considered successful)

## Scheduling

### Temporal Schedules

For automated execution, use Temporal schedules (configured separately):

```python
# Example schedule configuration (via Temporal CLI or SDK)
schedule = {
    "schedule_id": "food-truck-updates",
    "spec": {
        "cron_expressions": ["0 */6 * * *"]  # Every 6 hours
    },
    "action": {
        "start_workflow": {
            "workflow_type": "FoodTruckWorkflow",
            "task_queue": "food-truck-task-queue",
            "args": [{"deploy": True}]
        }
    }
}
```

### Manual Scheduling

For simple scheduling without Temporal schedules, use cron:

```bash
# Add to crontab for hourly updates
0 * * * * cd /path/to/project && uv run python -m around_the_grounds.temporal.starter --deploy
```

## Development and Testing

### Local Development

```bash
# Start local development server
temporal server start-dev

# Run worker
uv run python -m around_the_grounds.temporal.worker

# Test workflow
uv run python -m around_the_grounds.temporal.starter --verbose
```

### Integration Testing

```bash
# Test complete workflow execution
uv run python -m around_the_grounds.temporal.starter --deploy --verbose

# Verify results
ls -la public/data.json
git log --oneline -n 3
```

### Comparing with CLI

Validate that Temporal workflow produces identical results to CLI:

```bash
# CLI execution
uv run around-the-grounds | head -10

# Temporal execution  
uv run python -m around_the_grounds.temporal.starter | grep "Found"

# Should show same event count
```

## Production Deployment

### Worker Deployment

For production deployment:

```bash
# Run worker as systemd service
[Unit]
Description=Food Truck Temporal Worker
After=network.target

[Service]
Type=simple
User=temporal
WorkingDirectory=/path/to/project
ExecStart=/usr/local/bin/uv run python -m around_the_grounds.temporal.worker
Restart=always

[Install]
WantedBy=multi-user.target
```

### Environment Configuration

```bash
# Production environment variables
export TEMPORAL_ADDRESS="production-temporal:7233"
export ANTHROPIC_API_KEY="your-production-api-key"
export LOG_LEVEL="INFO"
```

### Monitoring

Set up monitoring for:
- Worker health and uptime
- Workflow success/failure rates
- Activity execution times
- Error frequencies

## Troubleshooting

### Common Issues

1. **Worker Won't Start**:
   - Check Temporal server connectivity
   - Verify dependencies are installed (`uv sync`)
   - Check for import errors in activities

2. **Workflows Not Executing**:
   - Ensure worker is running and connected
   - Check task queue name matches (`food-truck-task-queue`)
   - Verify workflow registration

3. **Activity Failures**:
   - Check network connectivity for scraping
   - Verify git repository setup for deployment
   - Review activity timeout settings

4. **Git Deployment Issues**:
   - Ensure git remote is configured
   - Check branch permissions
   - Verify git credentials are available

### Debug Commands

```bash
# Check worker connectivity
uv run python -c "
import asyncio
from around_the_grounds.temporal.activities import ScrapeActivities
async def test():
    activities = ScrapeActivities()
    result = await activities.test_connectivity()
    print(result)
asyncio.run(test())
"

# Test activity execution
uv run python -c "
import asyncio
from around_the_grounds.temporal.activities import ScrapeActivities
async def test():
    activities = ScrapeActivities()
    result = await activities.load_brewery_config()
    print(f'Loaded {len(result)} breweries')
asyncio.run(test())
"
```

## API Reference

### FoodTruckWorkflow.run(params: WorkflowParams) -> WorkflowResult

Main workflow that orchestrates the complete pipeline.

**Parameters:**
- `params`: WorkflowParams with configuration and deployment options

**Returns:**
- `WorkflowResult` with execution results and status

### ScrapeActivities

- `test_connectivity() -> str`: Test activity connectivity
- `load_brewery_config(config_path: Optional[str]) -> List[Dict]`: Load brewery configuration
- `scrape_food_trucks(brewery_configs: List[Dict]) -> Tuple[List[Dict], List[Dict]]`: Scrape events

### DeploymentActivities

- `generate_web_data(events: List[Dict]) -> Dict`: Generate web JSON
- `deploy_to_git(web_data: Dict) -> bool`: Deploy to git repository

For more details, see the comprehensive implementation plan in `TEMPORAL-PLAN.md`.