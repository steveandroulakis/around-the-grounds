"""Production-ready worker process for Temporal workflows."""

import asyncio
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from temporalio.client import Client
from temporalio.worker import Worker
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities

logger = logging.getLogger(__name__)


class FoodTruckWorker:
    """Production-ready worker for food truck workflows."""
    
    def __init__(self, temporal_address: str = "localhost:7233"):
        self.temporal_address = temporal_address
        self.client = None
        self.worker = None
        self.running = False
        self.shutdown_event = asyncio.Event()
    
    async def start(self):
        """Start the worker with proper error handling."""
        try:
            self.client = await Client.connect(self.temporal_address)
            logger.info(f"✅ Connected to Temporal at {self.temporal_address}")
            
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
                        scrape_activities.test_connectivity,
                        scrape_activities.load_brewery_config,
                        scrape_activities.scrape_food_trucks,
                        deploy_activities.generate_web_data,
                        deploy_activities.deploy_to_git,
                    ],
                    activity_executor=executor,
                )
                
                logger.info("🔧 Starting Temporal worker for food truck workflows...")
                logger.info("📋 Task queue: food-truck-task-queue")
                logger.info("💼 Max workers: 10")
                
                self.running = True
                
                # Run worker with shutdown handling
                worker_task = asyncio.create_task(self.worker.run())
                shutdown_task = asyncio.create_task(self.shutdown_event.wait())
                
                # Wait for either worker completion or shutdown signal
                done, pending = await asyncio.wait(
                    [worker_task, shutdown_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                
                logger.info("🛑 Worker stopped")
        
        except Exception as e:
            logger.error(f"❌ Worker failed to start: {e}")
            raise
    
    async def stop(self):
        """Gracefully stop the worker."""
        if self.running:
            logger.info("🛑 Stopping worker...")
            self.running = False
            self.shutdown_event.set()


async def main():
    """Main worker entry point with signal handling."""
    worker = FoodTruckWorker()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
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