"""Production-ready starter script for executing Temporal workflows."""

import asyncio
import argparse
import logging
import sys
from datetime import datetime
from typing import Optional
from temporalio.client import Client
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.shared import WorkflowParams

logger = logging.getLogger(__name__)


class FoodTruckStarter:
    """Production-ready starter for food truck workflows."""
    
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
    
    async def run_workflow(
        self,
        config_path: Optional[str] = None,
        deploy: bool = False,
        workflow_id: Optional[str] = None
    ):
        """Execute the food truck workflow."""
        if not self.client:
            await self.connect()
        
        if not workflow_id:
            workflow_id = f"food-truck-workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        try:
            logger.info(f"🚀 Starting workflow: {workflow_id}")
            logger.info(f"📂 Config path: {config_path or 'default'}")
            logger.info(f"🚀 Deploy: {deploy}")
            
            # Create workflow parameters
            params = WorkflowParams(
                config_path=config_path,
                deploy=deploy
            )
            
            handle = await self.client.start_workflow(
                FoodTruckWorkflow.run,
                params,
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
    """Main starter entry point with enhanced CLI arguments."""
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