"""Workflow definitions for Temporal."""

import asyncio
from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from .activities import DeploymentActivities, ScrapeActivities
    from .shared import WorkflowParams, WorkflowResult


@workflow.defn
class FoodTruckWorkflow:
    """Workflow for managing food truck data scraping and deployment."""

    @workflow.run
    async def run(self, params: WorkflowParams) -> WorkflowResult:
        """Execute the food truck workflow."""
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()

        try:
            # Step 1: Load brewery configuration
            venue_configs = await workflow.execute_activity(
                scrape_activities.load_brewery_config,
                params.config_path,
                schedule_to_close_timeout=timedelta(seconds=30),
            )

            workflow.logger.info(
                f"Loaded {len(venue_configs)} venue configurations"
            )

            # Step 2: Scrape food truck data across breweries in parallel batches
            max_parallel = max(1, params.max_parallel_scrapes)
            workflow.logger.info(
                f"Scraping venues with max_parallel_scrapes={max_parallel}"
            )

            all_events: List[Dict[str, Any]] = []
            all_errors: List[Dict[str, str]] = []

            if venue_configs:
                for start in range(0, len(venue_configs), max_parallel):
                    batch = venue_configs[start : start + max_parallel]
                    workflow.logger.info(
                        f"Launching scrape activities for venues {start + 1}-"
                        f"{start + len(batch)} of {len(venue_configs)}"
                    )

                    batch_results = await asyncio.gather(
                        *[
                            workflow.execute_activity(
                                scrape_activities.scrape_single_venue,
                                config,
                                schedule_to_close_timeout=timedelta(minutes=2),
                            )
                            for config in batch
                        ]
                    )

                    for result in batch_results:
                        all_events.extend(result.get("events", []))
                        error = result.get("error")
                        if error:
                            all_errors.append(error)

            events = all_events
            errors = all_errors

            workflow.logger.info(
                f"Scraped {len(events)} events with {len(errors)} errors"
            )

            # Step 3: Deploy if requested
            deployed = False
            if params.deploy and events:
                web_data = await workflow.execute_activity(
                    deploy_activities.generate_web_data,
                    {"events": events, "errors": errors},
                    schedule_to_close_timeout=timedelta(seconds=30),
                )

                deployed = await workflow.execute_activity(
                    deploy_activities.deploy_to_git,
                    {"web_data": web_data, "repository_url": params.git_repository_url},
                    schedule_to_close_timeout=timedelta(minutes=2),
                )

                workflow.logger.info(
                    f"Deployment {'successful' if deployed else 'failed'}"
                )

            return WorkflowResult(
                success=True,
                message=f"Workflow completed successfully. Found {len(events)} events.",
                events_count=len(events),
                errors=[error["message"] for error in errors],
                deployed=deployed,
            )

        except Exception as e:
            workflow.logger.error(f"Workflow failed: {str(e)}")
            return WorkflowResult(
                success=False,
                message=f"Workflow failed: {str(e)}",
                events_count=0,
                errors=[str(e)],
                deployed=False,
            )
