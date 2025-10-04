"""Workflow definitions for Temporal."""

from datetime import timedelta

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
            brewery_configs = await workflow.execute_activity(
                scrape_activities.load_brewery_config,
                params.config_path,
                schedule_to_close_timeout=timedelta(seconds=30),
            )

            workflow.logger.info(
                f"Loaded {len(brewery_configs)} brewery configurations"
            )

            # Step 2: Scrape food truck data
            events, errors = await workflow.execute_activity(
                scrape_activities.scrape_food_trucks,
                brewery_configs,
                schedule_to_close_timeout=timedelta(minutes=5),
            )

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
