"""Production-ready starter script for executing Temporal workflows."""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from typing import Optional

from temporalio.client import Client

from around_the_grounds.config.settings import get_git_repository_url
from around_the_grounds.temporal.config import (
    TEMPORAL_TASK_QUEUE,
    get_temporal_client,
    validate_configuration,
)
from around_the_grounds.temporal.shared import WorkflowParams, WorkflowResult
from around_the_grounds.temporal.workflows import FoodTruckWorkflow

logger = logging.getLogger(__name__)


class FoodTruckStarter:
    """Production-ready starter for food truck workflows."""

    def __init__(self, temporal_address: Optional[str] = None):
        # temporal_address parameter kept for backward compatibility
        # but actual connection uses environment configuration
        self.legacy_address = temporal_address
        self.client: Optional[Client] = None

    async def connect(self) -> None:
        """Connect to Temporal server using configuration system."""
        try:
            # Validate configuration before connecting
            validate_configuration()

            # Use the new configuration system instead of legacy address
            self.client = await get_temporal_client()

            if self.legacy_address and self.legacy_address != "localhost:7233":
                logger.warning(
                    f"⚠️  CLI --temporal-address={self.legacy_address} is deprecated."
                )
                logger.warning(
                    "⚠️  Please use TEMPORAL_ADDRESS environment variable instead."
                )

        except Exception as e:
            logger.error(f"❌ Failed to connect to Temporal: {e}")
            raise

    async def run_workflow(
        self,
        config_path: Optional[str] = None,
        deploy: bool = False,
        workflow_id: Optional[str] = None,
        git_repository_url: Optional[str] = None,
    ) -> WorkflowResult:
        """Execute the food truck workflow."""
        if not self.client:
            await self.connect()
        assert self.client is not None  # Type checker hint

        if not workflow_id:
            workflow_id = (
                f"food-truck-workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            )

        try:
            logger.info(f"🚀 Starting workflow: {workflow_id}")
            logger.info(f"📂 Config path: {config_path or 'default'}")
            logger.info(f"🚀 Deploy: {deploy}")

            # Get repository URL with fallback chain
            repository_url = get_git_repository_url(git_repository_url)
            logger.info(f"📍 Repository: {repository_url}")

            # Create workflow parameters
            params = WorkflowParams(
                config_path=config_path,
                deploy=deploy,
                git_repository_url=repository_url,
            )

            handle = await self.client.start_workflow(
                FoodTruckWorkflow.run,
                params,
                id=workflow_id,
                task_queue=TEMPORAL_TASK_QUEUE,
            )

            logger.info("⏳ Workflow started, waiting for completion...")
            result = await handle.result()

            logger.info("✅ Workflow completed!")
            logger.info(f"📊 Result: {result}")

            return result

        except Exception as e:
            logger.error(f"❌ Workflow execution failed: {e}")
            raise


async def main() -> None:
    """Main starter entry point with enhanced CLI arguments."""
    parser = argparse.ArgumentParser(description="Execute Food Truck Temporal Workflow")
    parser.add_argument(
        "--config", "-c", help="Path to brewery configuration JSON file"
    )
    parser.add_argument(
        "--deploy", "-d", action="store_true", help="Deploy results to web"
    )
    parser.add_argument("--workflow-id", help="Custom workflow ID")
    parser.add_argument(
        "--git-repo",
        help="Git repository URL for deployment (default: ballard-food-trucks)",
    )
    parser.add_argument(
        "--temporal-address",
        default="localhost:7233",
        help="Temporal server address (deprecated - use TEMPORAL_ADDRESS env var)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Show deprecation warning if --temporal-address is used with non-default value
    if args.temporal_address != "localhost:7233":
        logger.warning("⚠️  --temporal-address CLI argument is deprecated.")
        logger.warning("⚠️  Please use TEMPORAL_ADDRESS environment variable instead.")

    starter = FoodTruckStarter(args.temporal_address)

    try:
        result = await starter.run_workflow(
            config_path=args.config,
            deploy=args.deploy,
            workflow_id=args.workflow_id,
            git_repository_url=args.git_repo,
        )

        if result.success:
            print("✅ Workflow completed successfully!")
            print(f"📊 Found {result.events_count} events")
            if result.deployed:
                print("🚀 Successfully deployed to web")
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
