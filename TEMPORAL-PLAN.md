# Temporal Workflow Integration Plan

## Overview

This plan outlines the integration of Temporal workflow functionality into the Around the Grounds food truck tracking system. The goal is to run the existing crawling, data.json generation, git commit, and push operations as a Temporal workflow while maintaining all current functionality.

## Project Structure

```
around_the_grounds/
├── temporal/                    # New Temporal integration
│   ├── __init__.py
│   ├── workflows.py            # FoodTruckWorkflow definition
│   ├── activities.py           # ScrapeActivities + DeploymentActivities
│   ├── worker.py               # Worker process
│   ├── starter.py              # Manual workflow execution
│   └── shared.py               # Data classes and types
├── existing structure...
```

## Design Principles

1. **Zero Breaking Changes**: Existing CLI functionality preserved
2. **Minimal Code Duplication**: Activities wrap existing functionality
3. **Async Support**: Leverage existing async/await patterns
4. **Error Handling**: Preserve comprehensive error handling through activity isolation
5. **Extensibility**: Design allows for future scheduling integration

---

## Phase 1: Core Temporal Structure

### Objectives
- Create basic Temporal directory structure
- Add Temporal dependencies
- Implement minimal workflow and activity stubs
- Establish connectivity to local Temporal server

### Implementation Tasks

#### 1.1 Create Directory Structure
```bash
mkdir -p around_the_grounds/temporal
touch around_the_grounds/temporal/__init__.py
touch around_the_grounds/temporal/workflows.py
touch around_the_grounds/temporal/activities.py
touch around_the_grounds/temporal/shared.py
touch around_the_grounds/temporal/worker.py
touch around_the_grounds/temporal/starter.py
```

#### 1.2 Update Dependencies
Add to `pyproject.toml`:
```toml
dependencies = [
    # existing dependencies...
    "temporalio>=1.9.0",
]
```

#### 1.3 Create Basic Workflow Stub
`temporal/workflows.py`:
```python
from datetime import timedelta
from typing import Optional
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .activities import ScrapeActivities
    from .shared import WorkflowResult

@workflow.defn
class FoodTruckWorkflow:
    @workflow.run
    async def run(self, config_path: Optional[str] = None) -> WorkflowResult:
        # Stub implementation
        return WorkflowResult(success=True, message="Workflow stub executed")
```

#### 1.4 Create Basic Activity Stub
`temporal/activities.py`:
```python
from temporalio import activity
from .shared import WorkflowResult

class ScrapeActivities:
    @activity.defn
    async def test_connectivity(self) -> str:
        return "Activity connectivity test successful"
```

#### 1.5 Create Shared Data Models
`temporal/shared.py`:
```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class WorkflowResult:
    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
```

#### 1.6 Create Worker Stub
`temporal/worker.py`:
```python
import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from .workflows import FoodTruckWorkflow
from .activities import ScrapeActivities

async def main():
    client = await Client.connect("localhost:7233")
    activities = ScrapeActivities()
    
    worker = Worker(
        client,
        task_queue="food-truck-task-queue",
        workflows=[FoodTruckWorkflow],
        activities=[activities.test_connectivity],
    )
    
    print("🔧 Starting Temporal worker...")
    await worker.run()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

#### 1.7 Create Starter Stub
`temporal/starter.py`:
```python
import asyncio
from temporalio.client import Client
from .workflows import FoodTruckWorkflow

async def main():
    client = await Client.connect("localhost:7233")
    
    handle = await client.start_workflow(
        FoodTruckWorkflow.run,
        None,
        id="food-truck-workflow-test",
        task_queue="food-truck-task-queue",
    )
    
    print(f"Started workflow: {handle.id}")
    result = await handle.result()
    print(f"Result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 1 Validation Commands

```bash
# 1. Install dependencies
uv sync

# 2. Test worker can start (run in terminal 1)
cd around_the_grounds/temporal
python worker.py

# 3. Test workflow execution (run in terminal 2)
cd around_the_grounds/temporal
python starter.py

# 4. Verify workflow appears in Temporal UI
# Visit http://localhost:8233 and check for "food-truck-workflow-test"

# 5. Test existing CLI still works
uv run around-the-grounds --verbose
```

**Success Criteria for Phase 1:**
- [ ] Worker starts without errors
- [ ] Workflow executes and returns stub result
- [ ] Workflow appears in Temporal UI
- [ ] Existing CLI functionality unchanged
- [ ] No import or dependency errors

---

## Phase 2: Activity Implementation

### Objectives
- Implement ScrapeActivities wrapping existing scraping functionality
- Implement DeploymentActivities for git operations and web deployment
- Create ConfigActivities for brewery configuration management
- Maintain all existing error handling and logging

### Implementation Tasks

#### 2.1 Implement ScrapeActivities
`temporal/activities.py`:
```python
from temporalio import activity
from typing import List, Optional, Tuple
import asyncio
import logging

with activity.imports_passed_through():
    from ..models import Brewery, FoodTruckEvent
    from ..scrapers import ScraperCoordinator
    from ..main import load_brewery_config

class ScrapeActivities:
    @activity.defn
    async def load_brewery_config(self, config_path: Optional[str] = None) -> List[dict]:
        """Load brewery configuration and return as serializable data."""
        breweries = load_brewery_config(config_path)
        return [
            {
                "key": b.key,
                "name": b.name,
                "url": b.url,
                "parser_config": b.parser_config
            }
            for b in breweries
        ]
    
    @activity.defn
    async def scrape_food_trucks(self, brewery_configs: List[dict]) -> Tuple[List[dict], List[dict]]:
        """Scrape food truck data from all breweries."""
        # Convert dicts back to Brewery objects
        breweries = [
            Brewery(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                parser_config=config["parser_config"]
            )
            for config in brewery_configs
        ]
        
        coordinator = ScraperCoordinator()
        events = await coordinator.scrape_all(breweries)
        errors = coordinator.get_errors()
        
        # Convert to serializable format
        serialized_events = [
            {
                "date": event.date.isoformat(),
                "food_truck_name": event.food_truck_name,
                "brewery_name": event.brewery_name,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "description": event.description,
                "ai_generated_name": event.ai_generated_name,
            }
            for event in events
        ]
        
        serialized_errors = [
            {
                "brewery_name": error.brewery.name,
                "message": error.message
            }
            for error in errors
        ]
        
        return serialized_events, serialized_errors
```

#### 2.2 Implement DeploymentActivities
```python
class DeploymentActivities:
    @activity.defn
    async def generate_web_data(self, events: List[dict]) -> dict:
        """Generate web-friendly JSON data from events."""
        # Reconstruct events and use existing generate_web_data function
        from ..main import generate_web_data
        from ..models import FoodTruckEvent
        from datetime import datetime, time
        
        reconstructed_events = []
        for event_data in events:
            event = FoodTruckEvent(
                date=datetime.fromisoformat(event_data["date"]).date(),
                food_truck_name=event_data["food_truck_name"],
                brewery_name=event_data["brewery_name"],
                start_time=datetime.fromisoformat(event_data["start_time"]).time() if event_data["start_time"] else None,
                end_time=datetime.fromisoformat(event_data["end_time"]).time() if event_data["end_time"] else None,
                description=event_data["description"],
                ai_generated_name=event_data["ai_generated_name"],
            )
            reconstructed_events.append(event)
        
        return generate_web_data(reconstructed_events)
    
    @activity.defn
    async def deploy_to_git(self, web_data: dict) -> bool:
        """Deploy web data to git repository."""
        # Use existing deploy_to_web function logic
        from ..main import deploy_to_web
        from ..models import FoodTruckEvent
        from datetime import datetime
        
        # Reconstruct events for deployment
        reconstructed_events = []
        for event_data in web_data["events"]:
            # Convert web format back to FoodTruckEvent for deployment
            event = FoodTruckEvent(
                date=datetime.fromisoformat(event_data["date"]).date(),
                food_truck_name=event_data["vendor"].replace(" 🖼️🤖", ""),
                brewery_name=event_data["location"],
                start_time=datetime.strptime(event_data["start_time"], "%I:%M %p").time() if event_data["start_time"] else None,
                end_time=datetime.strptime(event_data["end_time"], "%I:%M %p").time() if event_data["end_time"] else None,
                description=event_data["description"],
                ai_generated_name=event_data.get("extraction_method") == "vision",
            )
            reconstructed_events.append(event)
        
        return deploy_to_web(reconstructed_events)
```

#### 2.3 Update Workflow Implementation
`temporal/workflows.py`:
```python
from datetime import timedelta
from typing import Optional
from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .activities import ScrapeActivities, DeploymentActivities
    from .shared import WorkflowResult

@workflow.defn
class FoodTruckWorkflow:
    @workflow.run
    async def run(self, config_path: Optional[str] = None, deploy: bool = False) -> WorkflowResult:
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        try:
            # Step 1: Load brewery configuration
            brewery_configs = await workflow.execute_activity_method(
                scrape_activities.load_brewery_config,
                config_path,
                schedule_to_close_timeout=timedelta(seconds=30),
            )
            
            # Step 2: Scrape food truck data
            events, errors = await workflow.execute_activity_method(
                scrape_activities.scrape_food_trucks,
                brewery_configs,
                schedule_to_close_timeout=timedelta(minutes=5),
            )
            
            # Step 3: Deploy if requested
            deployed = False
            if deploy and events:
                web_data = await workflow.execute_activity_method(
                    deploy_activities.generate_web_data,
                    events,
                    schedule_to_close_timeout=timedelta(seconds=30),
                )
                
                deployed = await workflow.execute_activity_method(
                    deploy_activities.deploy_to_git,
                    web_data,
                    schedule_to_close_timeout=timedelta(minutes=2),
                )
            
            return WorkflowResult(
                success=True,
                message=f"Workflow completed successfully. Found {len(events)} events.",
                events_count=len(events),
                errors=[error["message"] for error in errors],
                deployed=deployed,
            )
            
        except Exception as e:
            return WorkflowResult(
                success=False,
                message=f"Workflow failed: {str(e)}",
                events_count=0,
                errors=[str(e)],
                deployed=False,
            )
```

#### 2.4 Update Shared Data Models
`temporal/shared.py`:
```python
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class WorkflowResult:
    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
    deployed: bool = False
```

### Phase 2 Validation Commands

```bash
# 1. Test configuration loading activity
cd around_the_grounds/temporal
python -c "
import asyncio
from activities import ScrapeActivities
async def test():
    activities = ScrapeActivities()
    result = await activities.load_brewery_config()
    print(f'Loaded {len(result)} breweries')
asyncio.run(test())
"

# 2. Test full workflow with scraping (run worker first)
python worker.py &
python starter.py

# 3. Test workflow with deployment
python -c "
import asyncio
from temporalio.client import Client
from workflows import FoodTruckWorkflow

async def test_deploy():
    client = await Client.connect('localhost:7233')
    handle = await client.start_workflow(
        FoodTruckWorkflow.run,
        None, True,  # config_path=None, deploy=True
        id='food-truck-workflow-deploy-test',
        task_queue='food-truck-task-queue',
    )
    result = await handle.result()
    print(f'Deploy result: {result}')
asyncio.run(test_deploy())
"

# 4. Verify web deployment worked
ls -la public/data.json
git log --oneline -n 5
```

**Success Criteria for Phase 2:**
- [ ] Configuration loads successfully through activity
- [ ] Scraping completes and returns events
- [ ] Deployment activity generates data.json
- [ ] Git operations complete successfully
- [ ] All existing error handling preserved
- [ ] Workflow executes end-to-end without errors

---

## Phase 3: Worker & Execution Enhancement

### Objectives
- Enhance worker with production-ready configuration
- Improve error handling and logging
- Add monitoring and observability features
- Create robust starter script with options

### Implementation Tasks

#### 3.1 Enhanced Worker
`temporal/worker.py`:
```python
import asyncio
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from temporalio.client import Client
from temporalio.worker import Worker
from .workflows import FoodTruckWorkflow
from .activities import ScrapeActivities, DeploymentActivities

logger = logging.getLogger(__name__)

class FoodTruckWorker:
    def __init__(self, temporal_address: str = "localhost:7233"):
        self.temporal_address = temporal_address
        self.client = None
        self.worker = None
        self.running = False
    
    async def start(self):
        """Start the worker with proper error handling."""
        try:
            self.client = await Client.connect(self.temporal_address)
            
            # Initialize activities
            scrape_activities = ScrapeActivities()
            deploy_activities = DeploymentActivities()
            
            # Create worker with thread pool for blocking operations
            with ThreadPoolExecutor(max_workers=10) as executor:
                self.worker = Worker(
                    self.client,
                    task_queue="food-truck-task-queue",
                    workflows=[FoodTruckWorkflow],
                    activities=[
                        scrape_activities.load_brewery_config,
                        scrape_activities.scrape_food_trucks,
                        deploy_activities.generate_web_data,
                        deploy_activities.deploy_to_git,
                    ],
                    activity_executor=executor,
                )
                
                logger.info("🔧 Starting Temporal worker for food truck workflows...")
                logger.info(f"📍 Connected to Temporal at {self.temporal_address}")
                logger.info("📋 Task queue: food-truck-task-queue")
                
                self.running = True
                await self.worker.run()
        
        except Exception as e:
            logger.error(f"❌ Worker failed to start: {e}")
            raise
    
    async def stop(self):
        """Gracefully stop the worker."""
        if self.worker:
            logger.info("🛑 Stopping worker...")
            self.running = False
            # Worker will stop naturally when the context exits

async def main():
    """Main worker entry point with signal handling."""
    worker = FoodTruckWorker()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(worker.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await worker.start()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
```

#### 3.2 Enhanced Starter Script
`temporal/starter.py`:
```python
import asyncio
import argparse
import logging
import sys
from typing import Optional
from temporalio.client import Client
from .workflows import FoodTruckWorkflow

logger = logging.getLogger(__name__)

class FoodTruckStarter:
    def __init__(self, temporal_address: str = "localhost:7233"):
        self.temporal_address = temporal_address
        self.client = None
    
    async def connect(self):
        """Connect to Temporal server."""
        try:
            self.client = await Client.connect(self.temporal_address)
            logger.info(f"✅ Connected to Temporal at {self.temporal_address}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Temporal: {e}")
            raise
    
    async def run_workflow(self, config_path: Optional[str] = None, deploy: bool = False, workflow_id: Optional[str] = None):
        """Execute the food truck workflow."""
        if not self.client:
            await self.connect()
        
        if not workflow_id:
            from datetime import datetime
            workflow_id = f"food-truck-workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        try:
            logger.info(f"🚀 Starting workflow: {workflow_id}")
            logger.info(f"📂 Config path: {config_path or 'default'}")
            logger.info(f"🚀 Deploy: {deploy}")
            
            handle = await self.client.start_workflow(
                FoodTruckWorkflow.run,
                config_path,
                deploy,
                id=workflow_id,
                task_queue="food-truck-task-queue",
            )
            
            logger.info(f"⏳ Workflow started, waiting for completion...")
            result = await handle.result()
            
            logger.info(f"✅ Workflow completed!")
            logger.info(f"📊 Result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            raise

async def main():
    """Main starter entry point with CLI arguments."""
    parser = argparse.ArgumentParser(description="Execute Food Truck Temporal Workflow")
    parser.add_argument("--config", "-c", help="Path to brewery configuration JSON file")
    parser.add_argument("--deploy", "-d", action="store_true", help="Deploy results to web")
    parser.add_argument("--workflow-id", help="Custom workflow ID")
    parser.add_argument("--temporal-address", default="localhost:7233", help="Temporal server address")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    starter = FoodTruckStarter(args.temporal_address)
    
    try:
        result = await starter.run_workflow(
            config_path=args.config,
            deploy=args.deploy,
            workflow_id=args.workflow_id
        )
        
        if result.success:
            print(f"✅ Workflow completed successfully!")
            print(f"📊 Found {result.events_count} events")
            if result.deployed:
                print(f"🚀 Successfully deployed to web")
            if result.errors:
                print(f"⚠️  {len(result.errors)} errors occurred:")
                for error in result.errors:
                    print(f"   • {error}")
        else:
            print(f"❌ Workflow failed: {result.message}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Starter failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
```

### Phase 3 Validation Commands

```bash
# 1. Test enhanced worker startup
cd around_the_grounds/temporal
python worker.py

# 2. Test enhanced starter with options
python starter.py --verbose --deploy

# 3. Test workflow with custom ID
python starter.py --workflow-id my-test-workflow --config ../config/breweries.json

# 4. Test graceful shutdown (Ctrl+C the worker)
python worker.py
# Press Ctrl+C and verify clean shutdown

# 5. Monitor workflow in Temporal UI
# Visit http://localhost:8233 and verify workflow execution details
```

**Success Criteria for Phase 3:**
- [ ] Worker starts and stops gracefully
- [ ] Enhanced logging provides clear visibility
- [ ] Starter script accepts all CLI arguments
- [ ] Workflow execution is visible in Temporal UI
- [ ] Error handling works for various failure scenarios
- [ ] Thread pool executor handles activities properly

---

## Phase 4: Testing & Validation

### Objectives
- Create comprehensive test suite for Temporal components
- Validate error handling and edge cases
- Ensure no regression in existing functionality
- Test scheduling integration (if applicable)

### Implementation Tasks

#### 4.1 Create Test Structure
```bash
mkdir -p tests/temporal
touch tests/temporal/__init__.py
touch tests/temporal/test_workflows.py
touch tests/temporal/test_activities.py
touch tests/temporal/test_integration.py
```

#### 4.2 Workflow Tests
`tests/temporal/test_workflows.py`:
```python
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities

@pytest.mark.asyncio
async def test_food_truck_workflow_success():
    """Test successful workflow execution."""
    async with WorkflowEnvironment() as env:
        # Setup activities
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()
        
        # Create worker
        async with Worker(
            env.client,
            task_queue="test-task-queue",
            workflows=[FoodTruckWorkflow],
            activities=[
                scrape_activities.load_brewery_config,
                scrape_activities.scrape_food_trucks,
                deploy_activities.generate_web_data,
                deploy_activities.deploy_to_git,
            ],
        ):
            # Execute workflow
            result = await env.client.execute_workflow(
                FoodTruckWorkflow.run,
                None,
                False,
                id="test-workflow",
                task_queue="test-task-queue",
            )
            
            assert result.success
            assert result.events_count >= 0
            assert result.deployed is False

@pytest.mark.asyncio
async def test_food_truck_workflow_with_deploy():
    """Test workflow with deployment enabled."""
    async with WorkflowEnvironment() as env:
        # Similar setup but with deploy=True
        # Mock git operations for testing
        pass
```

#### 4.3 Activity Tests
`tests/temporal/test_activities.py`:
```python
import pytest
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities

@pytest.mark.asyncio
async def test_scrape_activities_load_config():
    """Test brewery configuration loading."""
    activities = ScrapeActivities()
    result = await activities.load_brewery_config()
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert "name" in result[0]
    assert "url" in result[0]

@pytest.mark.asyncio
async def test_scrape_activities_scrape_food_trucks(mock_brewery_configs):
    """Test food truck scraping activity."""
    activities = ScrapeActivities()
    events, errors = await activities.scrape_food_trucks(mock_brewery_configs)
    
    assert isinstance(events, list)
    assert isinstance(errors, list)
```

#### 4.4 Integration Tests
`tests/temporal/test_integration.py`:
```python
import pytest
import asyncio
from temporalio.client import Client
from temporalio.worker import Worker
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities

@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_workflow():
    """Test complete workflow execution against real Temporal server."""
    try:
        client = await Client.connect("localhost:7233")
        
        # Start workflow
        handle = await client.start_workflow(
            FoodTruckWorkflow.run,
            None,
            False,
            id="integration-test-workflow",
            task_queue="food-truck-task-queue",
        )
        
        # Wait for completion
        result = await handle.result()
        
        assert result.success
        assert result.events_count >= 0
        
    except Exception as e:
        pytest.skip(f"Temporal server not available: {e}")
```

### Phase 4 Validation Commands

```bash
# 1. Run unit tests
uv run python -m pytest tests/temporal/test_activities.py -v

# 2. Run workflow tests
uv run python -m pytest tests/temporal/test_workflows.py -v

# 3. Run integration tests (requires Temporal server)
uv run python -m pytest tests/temporal/test_integration.py -v -m integration

# 4. Run full test suite
uv run python -m pytest tests/ -v

# 5. Test existing functionality still works
uv run around-the-grounds --verbose
uv run around-the-grounds --deploy

# 6. Performance test - compare execution times
time uv run around-the-grounds
time python temporal/starter.py

# 7. Error handling test - break configuration and verify graceful failure
cp config/breweries.json config/breweries.json.backup
echo "invalid json" > config/breweries.json
python temporal/starter.py --config config/breweries.json
mv config/breweries.json.backup config/breweries.json
```

**Success Criteria for Phase 4:**
- [ ] All temporal tests pass
- [ ] All existing tests continue to pass
- [ ] Integration tests work with real Temporal server
- [ ] Error handling works for various failure scenarios
- [ ] Performance is comparable to existing CLI
- [ ] No regression in existing functionality

---

## Final Validation & Documentation

### Complete System Test
```bash
# 1. Start worker in background
cd around_the_grounds/temporal
python worker.py &
WORKER_PID=$!

# 2. Run workflow with deployment
python starter.py --deploy --verbose

# 3. Verify results
ls -la ../public/data.json
git log --oneline -n 3

# 4. Stop worker
kill $WORKER_PID

# 5. Verify existing CLI still works
cd ..
uv run around-the-grounds --deploy
```

### Usage Documentation
Create final documentation in `temporal/README.md` covering:
- Worker startup procedures
- Workflow execution options
- Scheduling integration steps
- Monitoring and observability
- Troubleshooting common issues

## Success Metrics

Upon completion, the system should:
- ✅ Execute the complete food truck workflow via Temporal
- ✅ Maintain 100% backward compatibility with existing CLI
- ✅ Provide comprehensive error handling and logging
- ✅ Support both manual execution and scheduled runs
- ✅ Integrate seamlessly with existing git deployment workflow
- ✅ Offer visibility through Temporal UI
- ✅ Handle all edge cases and error scenarios gracefully

## Next Steps After Implementation

1. **Scheduling Integration**: Connect to Temporal schedules for automated runs
2. **Monitoring**: Add metrics and alerting for workflow health
3. **Multi-Environment**: Support for different deployment environments
4. **Advanced Features**: Workflow versioning, signal handling, queries
5. **Performance Optimization**: Optimize for high-frequency execution