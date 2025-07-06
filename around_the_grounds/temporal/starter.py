"""Starter script for executing Temporal workflows."""

import asyncio
import argparse
from datetime import datetime
from temporalio.client import Client
from around_the_grounds.temporal.workflows import FoodTruckWorkflow
from around_the_grounds.temporal.shared import WorkflowParams


async def main():
    """Main starter entry point."""
    parser = argparse.ArgumentParser(description="Execute Food Truck Temporal Workflow")
    parser.add_argument("--config", "-c", help="Path to brewery configuration JSON file")
    parser.add_argument("--deploy", "-d", action="store_true", help="Deploy results to web")
    parser.add_argument("--workflow-id", help="Custom workflow ID")
    
    args = parser.parse_args()
    
    client = await Client.connect("localhost:7233")
    
    # Generate workflow ID if not provided
    workflow_id = args.workflow_id or f"food-truck-workflow-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    print(f"🚀 Starting workflow: {workflow_id}")
    print(f"📂 Config: {args.config or 'default'}")
    print(f"🚀 Deploy: {args.deploy}")
    
    # Create workflow parameters
    params = WorkflowParams(
        config_path=args.config,
        deploy=args.deploy
    )
    
    handle = await client.start_workflow(
        FoodTruckWorkflow.run,
        params,
        id=workflow_id,
        task_queue="food-truck-task-queue",
    )
    
    print(f"⏳ Workflow started, waiting for completion...")
    result = await handle.result()
    
    print(f"✅ Workflow completed!")
    print(f"📊 Result: {result}")
    
    if result.success:
        print(f"📊 Found {result.events_count} events")
        if result.deployed:
            print(f"🚀 Successfully deployed to web")
        if result.errors:
            print(f"⚠️  {len(result.errors)} errors occurred:")
            for error in result.errors:
                print(f"   • {error}")
    else:
        print(f"❌ Workflow failed: {result.message}")


if __name__ == "__main__":
    asyncio.run(main())