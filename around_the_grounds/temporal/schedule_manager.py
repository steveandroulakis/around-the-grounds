"""Schedule management script for Food Truck Temporal workflows.

This script provides comprehensive schedule management capabilities:
- Create schedules with configurable intervals
- List, describe, delete, and manage existing schedules
- Support for all Temporal deployment modes (local, cloud, mTLS)
- Integration with existing workflow and configuration system
"""

import argparse
import asyncio
import logging
import sys
from datetime import timedelta
from typing import Any, Dict, List, Optional, cast

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
)

from .config import TEMPORAL_TASK_QUEUE, get_temporal_client, validate_configuration
from .shared import WorkflowParams
from .workflows import FoodTruckWorkflow

logger = logging.getLogger(__name__)


class ScheduleManager:
    """Comprehensive schedule management for Food Truck workflows."""

    def __init__(self) -> None:
        self.client: Optional[Client] = None

    async def connect(self) -> None:
        """Connect to Temporal server using configuration system."""
        try:
            validate_configuration()
            self.client = await get_temporal_client()
            logger.info("✅ Connected to Temporal server")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Temporal: {e}")
            raise

    async def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if self.client is None:
            await self.connect()

    async def create_schedule(
        self,
        schedule_id: str,
        interval_minutes: int,
        config_path: Optional[str] = None,
        deploy: bool = True,
        note: Optional[str] = None,
        paused: bool = False,
    ) -> str:
        """
        Create a new schedule for the Food Truck workflow.

        Args:
            schedule_id: Unique identifier for the schedule
            interval_minutes: Interval in minutes between workflow executions
            config_path: Path to brewery configuration file
            deploy: Whether to deploy results to web
            note: Optional note about the schedule
            paused: Whether to create the schedule in paused state

        Returns:
            Schedule ID of the created schedule
        """
        await self._ensure_connected()

        try:
            # Create workflow parameters
            params = WorkflowParams(config_path=config_path, deploy=deploy)

            # Default note if not provided
            if not note:
                note = f"Food Truck data scraping and deployment every {interval_minutes} minutes"

            # Create schedule configuration
            schedule = Schedule(
                action=ScheduleActionStartWorkflow(
                    FoodTruckWorkflow.run,
                    params,
                    id=f"food-truck-workflow-{schedule_id}",
                    task_queue=TEMPORAL_TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[
                        ScheduleIntervalSpec(every=timedelta(minutes=interval_minutes))
                    ]
                ),
                state=ScheduleState(
                    note=note,
                    paused=paused,
                ),
            )

            # Create the schedule
            await self._ensure_connected()
            assert self.client is not None  # Type checker hint
            await self.client.create_schedule(schedule_id, schedule)

            logger.info(
                f"✅ Created schedule '{schedule_id}' with {interval_minutes} minute interval"
            )
            logger.info(f"📋 Note: {note}")
            if paused:
                logger.info("⏸️  Schedule created in paused state")

            return schedule_id

        except Exception as e:
            logger.error(f"❌ Failed to create schedule: {e}")
            raise

    async def list_schedules(self) -> List[str]:
        """List all existing schedules."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            schedules = []
            async for schedule in await self.client.list_schedules():
                schedules.append(schedule.id)
                logger.info(f"📅 Schedule: {schedule.id}")
                logger.info(f"   Info: {schedule.info}")

            if not schedules:
                logger.info("📭 No schedules found")

            return schedules

        except Exception as e:
            logger.error(f"❌ Failed to list schedules: {e}")
            raise

    async def describe_schedule(self, schedule_id: str) -> dict:
        """Get detailed information about a specific schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)
            desc = await handle.describe()

            # Extract key information
            info: Dict[str, Any] = {
                "id": schedule_id,
                "note": desc.schedule.state.note,
                "paused": desc.schedule.state.paused,
                "intervals": [],
                "next_actions": [],
                "recent_actions": [],
            }

            # Get interval information
            if desc.schedule.spec.intervals:
                for interval in desc.schedule.spec.intervals:
                    cast(List[Any], info["intervals"]).append(
                        {
                            "every": str(interval.every),
                            "offset": str(interval.offset) if interval.offset else None,
                        }
                    )

            # Get next actions
            for action in desc.info.next_action_times[:5]:  # Show next 5
                cast(List[Any], info["next_actions"]).append(action.isoformat())

            # Get recent actions
            for recent_action in desc.info.recent_actions[-5:]:  # Show last 5
                action_info: Dict[str, Any] = {}

                # Use try/except to handle attributes that may not exist in all SDK versions
                try:
                    if (
                        hasattr(recent_action, "scheduled_time")
                        and recent_action.scheduled_time  # type: ignore[attr-defined]
                    ):
                        action_info["scheduled_time"] = (
                            recent_action.scheduled_time.isoformat()  # type: ignore[attr-defined]
                        )
                except AttributeError:
                    pass

                try:
                    if (
                        hasattr(recent_action, "actual_time")
                        and recent_action.actual_time  # type: ignore[attr-defined]
                    ):
                        action_info["actual_time"] = (
                            recent_action.actual_time.isoformat()  # type: ignore[attr-defined]
                        )
                except AttributeError:
                    pass

                try:
                    if (
                        hasattr(recent_action, "start_workflow_result")
                        and recent_action.start_workflow_result  # type: ignore[attr-defined]
                    ):
                        if hasattr(recent_action.start_workflow_result, "workflow_id"):  # type: ignore[attr-defined]
                            action_info["workflow_id"] = (
                                recent_action.start_workflow_result.workflow_id  # type: ignore[attr-defined]
                            )
                except AttributeError:
                    pass

                cast(List[Any], info["recent_actions"]).append(action_info)

            logger.info(f"📋 Schedule Details for '{schedule_id}':")
            logger.info(f"   Note: {info['note']}")
            logger.info(f"   Paused: {info['paused']}")
            logger.info(f"   Intervals: {info['intervals']}")
            logger.info(
                f"   Next {len(cast(List[Any], info['next_actions']))} actions: {info['next_actions']}"
            )
            logger.info(
                f"   Recent {len(cast(List[Any], info['recent_actions']))} actions: {len(cast(List[Any], info['recent_actions']))}"
            )

            return info

        except Exception as e:
            logger.error(f"❌ Failed to describe schedule '{schedule_id}': {e}")
            raise

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)
            await handle.delete()
            logger.info(f"🗑️  Deleted schedule '{schedule_id}'")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to delete schedule '{schedule_id}': {e}")
            raise

    async def pause_schedule(
        self, schedule_id: str, note: Optional[str] = None
    ) -> bool:
        """Pause a schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)
            await handle.pause(note=note)
            logger.info(f"⏸️  Paused schedule '{schedule_id}'")
            if note:
                logger.info(f"📝 Note: {note}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to pause schedule '{schedule_id}': {e}")
            raise

    async def unpause_schedule(
        self, schedule_id: str, note: Optional[str] = None
    ) -> bool:
        """Unpause a schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)
            await handle.unpause(note=note)
            logger.info(f"▶️  Unpaused schedule '{schedule_id}'")
            if note:
                logger.info(f"📝 Note: {note}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to unpause schedule '{schedule_id}': {e}")
            raise

    async def trigger_schedule(self, schedule_id: str) -> bool:
        """Trigger an immediate execution of a schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)
            await handle.trigger()
            logger.info(f"🚀 Triggered immediate execution of schedule '{schedule_id}'")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to trigger schedule '{schedule_id}': {e}")
            raise

    async def update_schedule_interval(
        self, schedule_id: str, new_interval_minutes: int
    ) -> bool:
        """Update the interval of an existing schedule."""
        await self._ensure_connected()
        assert self.client is not None  # Type checker hint

        try:
            handle = self.client.get_schedule_handle(schedule_id)

            # Get current schedule
            desc = await handle.describe()
            current_schedule = desc.schedule

            # Update the interval
            current_schedule.spec.intervals = [
                ScheduleIntervalSpec(every=timedelta(minutes=new_interval_minutes))
            ]

            # Update the schedule
            from temporalio.client import ScheduleUpdateInput

            async def updater(_input: ScheduleUpdateInput) -> ScheduleUpdate:
                return ScheduleUpdate(schedule=current_schedule)

            await handle.update(updater=updater)

            logger.info(
                f"🔄 Updated schedule '{schedule_id}' to {new_interval_minutes} minute interval"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Failed to update schedule '{schedule_id}': {e}")
            raise


async def main() -> None:
    """Main CLI interface for schedule management."""
    parser = argparse.ArgumentParser(
        description="Manage Food Truck Temporal workflow schedules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a schedule that runs every 30 minutes
  python -m around_the_grounds.temporal.schedule_manager create --schedule-id daily-scrape --interval 30
  
  # Create a schedule with custom config and paused
  python -m around_the_grounds.temporal.schedule_manager create --schedule-id custom-scrape --interval 60 --config /path/to/config.json --paused
  
  # List all schedules
  python -m around_the_grounds.temporal.schedule_manager list
  
  # Describe a specific schedule
  python -m around_the_grounds.temporal.schedule_manager describe --schedule-id daily-scrape
  
  # Pause a schedule
  python -m around_the_grounds.temporal.schedule_manager pause --schedule-id daily-scrape --note "Maintenance window"
  
  # Unpause a schedule
  python -m around_the_grounds.temporal.schedule_manager unpause --schedule-id daily-scrape
  
  # Trigger immediate execution
  python -m around_the_grounds.temporal.schedule_manager trigger --schedule-id daily-scrape
  
  # Update schedule interval
  python -m around_the_grounds.temporal.schedule_manager update --schedule-id daily-scrape --interval 45
  
  # Delete a schedule
  python -m around_the_grounds.temporal.schedule_manager delete --schedule-id daily-scrape
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create schedule command
    create_parser = subparsers.add_parser("create", help="Create a new schedule")
    create_parser.add_argument(
        "--schedule-id", required=True, help="Unique schedule identifier"
    )
    create_parser.add_argument(
        "--interval",
        type=int,
        required=True,
        help="Interval in minutes between executions",
    )
    create_parser.add_argument("--config", help="Path to brewery configuration file")
    create_parser.add_argument(
        "--no-deploy", action="store_true", help="Don't deploy results to web"
    )
    create_parser.add_argument("--note", help="Optional note about the schedule")
    create_parser.add_argument(
        "--paused", action="store_true", help="Create schedule in paused state"
    )

    # List schedules command
    _ = subparsers.add_parser("list", help="List all schedules")

    # Describe schedule command
    describe_parser = subparsers.add_parser(
        "describe", help="Describe a specific schedule"
    )
    describe_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )

    # Delete schedule command
    delete_parser = subparsers.add_parser("delete", help="Delete a schedule")
    delete_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )

    # Pause schedule command
    pause_parser = subparsers.add_parser("pause", help="Pause a schedule")
    pause_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )
    pause_parser.add_argument("--note", help="Optional note about why pausing")

    # Unpause schedule command
    unpause_parser = subparsers.add_parser("unpause", help="Unpause a schedule")
    unpause_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )
    unpause_parser.add_argument("--note", help="Optional note about why unpausing")

    # Trigger schedule command
    trigger_parser = subparsers.add_parser(
        "trigger", help="Trigger immediate execution"
    )
    trigger_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )

    # Update schedule command
    update_parser = subparsers.add_parser("update", help="Update schedule interval")
    update_parser.add_argument(
        "--schedule-id", required=True, help="Schedule identifier"
    )
    update_parser.add_argument(
        "--interval", type=int, required=True, help="New interval in minutes"
    )

    # Global arguments
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if not args.command:
        parser.print_help()
        return

    manager = ScheduleManager()

    try:
        if args.command == "create":
            await manager.create_schedule(
                schedule_id=args.schedule_id,
                interval_minutes=args.interval,
                config_path=args.config,
                deploy=not args.no_deploy,
                note=args.note,
                paused=args.paused,
            )
        elif args.command == "list":
            await manager.list_schedules()
        elif args.command == "describe":
            await manager.describe_schedule(args.schedule_id)
        elif args.command == "delete":
            await manager.delete_schedule(args.schedule_id)
        elif args.command == "pause":
            await manager.pause_schedule(args.schedule_id, args.note)
        elif args.command == "unpause":
            await manager.unpause_schedule(args.schedule_id, args.note)
        elif args.command == "trigger":
            await manager.trigger_schedule(args.schedule_id)
        elif args.command == "update":
            await manager.update_schedule_interval(args.schedule_id, args.interval)
        else:
            parser.print_help()

    except Exception as e:
        logger.error(f"❌ Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
