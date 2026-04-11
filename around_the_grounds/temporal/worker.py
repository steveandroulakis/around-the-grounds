"""Production-ready worker process for Temporal workflows."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from temporalio.worker import Worker

from around_the_grounds.temporal.activities import (
    DeploymentActivities,
    ScrapeActivities,
)
from around_the_grounds.temporal.config import (
    TEMPORAL_TASK_QUEUE,
    get_temporal_client,
    validate_configuration,
)
from around_the_grounds.temporal.workflows import FoodTruckWorkflow

logger = logging.getLogger(__name__)


async def main() -> None:
    """Main worker entry point."""
    # Validate configuration before connecting
    try:
        validate_configuration()
    except Exception as e:
        logger.error(f"❌ Configuration validation failed: {e}")
        raise

    # Create the client using configuration
    client = await get_temporal_client()

    # Initialize activities
    scrape_activities = ScrapeActivities()
    deploy_activities = DeploymentActivities()

    logger.info("🔧 Starting Temporal worker for food truck workflows...")
    logger.info(f"📋 Task queue: {TEMPORAL_TASK_QUEUE}")
    logger.info("💼 Max workers: 10")

    # Run the worker with proper cleanup
    try:
        with ThreadPoolExecutor(max_workers=10) as activity_executor:
            worker = Worker(
                client,
                task_queue=TEMPORAL_TASK_QUEUE,
                workflows=[FoodTruckWorkflow],
                activities=[
                    scrape_activities.test_connectivity,
                    scrape_activities.load_site,
                    scrape_activities.scrape_single_venue,
                    deploy_activities.generate_web_data,
                    deploy_activities.deploy_to_git,
                ],
                activity_executor=activity_executor,
            )

            logger.info("Worker ready to process tasks!")
            await worker.run()

    except KeyboardInterrupt:
        logger.info("🛑 Worker interrupted by user")
    except Exception as e:
        logger.error(f"Worker error: {e}")
        raise
    finally:
        logger.info("🛑 Worker stopped")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
