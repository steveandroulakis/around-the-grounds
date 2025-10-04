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
├── config.py          # Temporal client configuration system
├── schedule_manager.py # Comprehensive schedule management script
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
- **ScheduleManager**: Comprehensive schedule management with configurable intervals and full lifecycle operations

## Quick Start

### Prerequisites

1. **Temporal Server**: Local server on `localhost:7233`, Temporal Cloud, or custom deployment
2. **Dependencies**: Run `uv sync` to install all dependencies including `temporalio`
3. **Environment**: Set up authentication and configuration (see Configuration section below)

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

## Configuration

The system supports multiple deployment scenarios through environment-based configuration. All configuration is handled automatically - just set the appropriate environment variables and the system will connect to the right Temporal server with the correct authentication.

### Local Development (Default)

No configuration needed - connects to `localhost:7233` automatically:

```bash
# No environment variables needed
uv run python -m around_the_grounds.temporal.worker
uv run python -m around_the_grounds.temporal.starter --deploy
```

### Temporal Cloud

Set environment variables for Temporal Cloud with API key authentication:

```bash
# Required for Temporal Cloud
export TEMPORAL_ADDRESS="your-namespace.acct.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"  
export TEMPORAL_API_KEY="your-api-key"

# Optional: Custom task queue
export TEMPORAL_TASK_QUEUE="food-truck-task-queue"

# Run worker and starter - automatically connects to Temporal Cloud
uv run python -m around_the_grounds.temporal.worker
uv run python -m around_the_grounds.temporal.starter --deploy
```

**Getting Temporal Cloud Credentials:**
1. Sign up at [cloud.temporal.io](https://cloud.temporal.io)
2. Create a namespace
3. Generate an API key from the namespace settings
4. Use the connection details provided in the UI

### Custom Server with mTLS

For enterprise deployments with certificate-based authentication:

```bash
# Required for mTLS authentication
export TEMPORAL_ADDRESS="your-server.example.com:7233"
export TEMPORAL_NAMESPACE="production"
export TEMPORAL_TLS_CERT="/path/to/client.pem"
export TEMPORAL_TLS_KEY="/path/to/client.key"

# Optional: Custom task queue
export TEMPORAL_TASK_QUEUE="production-task-queue"

# Run worker and starter - automatically uses mTLS
uv run python -m around_the_grounds.temporal.worker
uv run python -m around_the_grounds.temporal.starter --deploy
```

### Environment Files

For persistent configuration, create a `.env` file:

```bash
# Copy the template
cp .env.example .env

# Edit with your configuration
# Example for Temporal Cloud:
TEMPORAL_ADDRESS=my-namespace.acct.tmprl.cloud:7233
TEMPORAL_NAMESPACE=my-namespace
TEMPORAL_API_KEY=abcdef1234567890

# Food truck application settings
ANTHROPIC_API_KEY=your-anthropic-key
VISION_ANALYSIS_ENABLED=true
```

### Configuration Validation

The system validates configuration on startup and provides helpful error messages:

```bash
# Example successful connection to Temporal Cloud
🔗 Connecting to Temporal server:
   Address: my-namespace.acct.tmprl.cloud:7233
   Namespace: my-namespace
   Task Queue: food-truck-task-queue
   Mode: Remote server
   API Key: abcdef12...
   Authentication: API Key
✅ Configuration validation passed
✅ Connected to Temporal successfully
```

### Legacy CLI Arguments (Deprecated)

CLI arguments still work but show deprecation warnings:

```bash
# This still works but is deprecated
uv run python -m around_the_grounds.temporal.starter --temporal-address production:7233 --deploy

# Output includes deprecation warning:
⚠️ --temporal-address CLI argument is deprecated.
⚠️ Please use TEMPORAL_ADDRESS environment variable instead.
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

- `generate_web_data(events, error_messages=None)`: Generate web-friendly JSON from events and include any user-facing errors
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

### Temporal Schedule Management

The system includes a comprehensive schedule management script that supports creating, managing, and monitoring schedules with configurable intervals:

#### Creating Schedules

```bash
# Create a schedule that runs every 30 minutes
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30

# Create a schedule with custom config and start paused
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id custom-scrape --interval 60 --config /path/to/config.json --paused

# Create a schedule without web deployment
uv run python -m around_the_grounds.temporal.schedule_manager create --schedule-id scrape-only --interval 45 --no-deploy
```

#### Managing Schedules

```bash
# List all schedules
uv run python -m around_the_grounds.temporal.schedule_manager list

# Describe a specific schedule
uv run python -m around_the_grounds.temporal.schedule_manager describe --schedule-id daily-scrape

# Pause a schedule with a note
uv run python -m around_the_grounds.temporal.schedule_manager pause --schedule-id daily-scrape --note "Maintenance window"

# Unpause a schedule
uv run python -m around_the_grounds.temporal.schedule_manager unpause --schedule-id daily-scrape

# Trigger immediate execution
uv run python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape

# Update schedule interval to 45 minutes
uv run python -m around_the_grounds.temporal.schedule_manager update --schedule-id daily-scrape --interval 45

# Delete a schedule
uv run python -m around_the_grounds.temporal.schedule_manager delete --schedule-id daily-scrape
```

#### Schedule Features

- **Configurable Intervals**: Set any interval in minutes (e.g., 5, 30, 60, 120)
- **Multiple Deployment Modes**: Works with local, Temporal Cloud, and mTLS configurations
- **Comprehensive Management**: Create, list, describe, pause, unpause, trigger, update, and delete
- **Production Ready**: Built-in error handling and detailed logging
- **Custom Configuration**: Support for custom brewery configs and workflow parameters

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

### Running a Worker Locally

For production use, simply run the worker with appropriate environment variables:

```bash
# Set your production environment variables
export TEMPORAL_ADDRESS="your-namespace.acct.tmprl.cloud:7233"
export TEMPORAL_NAMESPACE="your-namespace"
export TEMPORAL_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-production-api-key"

# Run the worker
uv run python -m around_the_grounds.temporal.worker
```

The worker will:
- Connect to your configured Temporal server
- Run continuously processing workflows
- Handle graceful shutdown with Ctrl+C
- Automatically reconnect on connection issues

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

- `generate_web_data(payload: Dict[str, Any]) -> Dict`: Generate web JSON from events and errors
- `deploy_to_git(web_data: Dict) -> bool`: Deploy to git repository

For more details, see the comprehensive implementation plan in `TEMPORAL-PLAN.md`.
