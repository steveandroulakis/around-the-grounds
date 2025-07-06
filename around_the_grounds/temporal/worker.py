"""Worker implementation for Temporal workflows."""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.activities import ScrapeActivities, DeploymentActivities


async def main():
    """Main worker entry point."""
    client = await Client.connect("localhost:7233")
    scrape_activities = ScrapeActivities()
    deploy_activities = DeploymentActivities()
    
    worker = Worker(
        client,
        task_queue="food-truck-task-queue",
        workflows=[FoodTruckWorkflow],
        activities=[
            scrape_activities.test_connectivity,
            scrape_activities.load_brewery_config,
            scrape_activities.scrape_food_trucks,
            deploy_activities.generate_web_data,
            deploy_activities.deploy_to_git,
        ],
    )
    
    print("🔧 Starting Temporal worker...")
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())