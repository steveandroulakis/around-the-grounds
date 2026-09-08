"""Workflow definitions for Temporal."""

import asyncio
from datetime import timedelta
from typing import Any, Dict, List

from temporalio import workflow
from temporalio.exceptions import (
    ActivityError,
    ApplicationError,
    is_cancelled_exception,
)

with workflow.unsafe.imports_passed_through():
    from .activities import DeploymentActivities, ScrapeActivities
    from .shared import WorkflowParams, WorkflowResult

# The scrape activity runs the coordinator's own retry loop (3 attempts x 60s
# HTTP timeout plus backoff, ~3 minutes worst case). The per-attempt timeout
# must contain that, or Temporal kills the attempt before the coordinator can
# report a clean per-venue error. schedule_to_close leaves room for one
# Temporal-level retry on infrastructure failure (worker loss, etc.).
SCRAPE_START_TO_CLOSE = timedelta(minutes=4)
SCRAPE_SCHEDULE_TO_CLOSE = timedelta(minutes=5)

DEFAULT_SITE_KEY = "ballard-food-trucks"
DEFAULT_SITE_TIMEZONE = "America/Los_Angeles"


@workflow.defn
class FoodTruckWorkflow:
    """Workflow for managing food truck data scraping and deployment.

    Outcome contract:

    - Completed with ``WorkflowResult`` when at least one venue produced
      events (or the schedule is genuinely empty with no errors). Partial
      venue failures are listed in ``errors``.
    - Failed (``ApplicationError``) when every venue failed, when a requested
      deploy did not succeed, or when an unexpected exception occurred. This
      keeps failures visible in Temporal (UI, list filters, metrics) instead
      of buried inside a Completed result. Failing rather than letting the
      workflow task retry also guarantees the next scheduled run is not
      skipped by a stuck execution.
    - Cancelled when cancellation arrives; cancellation is never converted
      into a result and never leads to a deploy.
    """

    @workflow.run
    async def run(self, params: WorkflowParams) -> WorkflowResult:
        """Execute the food truck workflow."""
        try:
            return await self._run(params)
        except Exception as e:
            # Let Temporal's own failure types (and cancellation, which the
            # SDK may wrap in an ActivityError) propagate untouched.
            if is_cancelled_exception(e) or isinstance(
                e, (ApplicationError, ActivityError)
            ):
                raise
            # Any other exception would fail the *workflow task* and be
            # retried forever, leaving the execution stuck in Running and
            # causing the schedule to skip subsequent runs. Fail the
            # execution instead so the next scheduled run proceeds.
            workflow.logger.error(f"Workflow failed: {e}")
            raise ApplicationError(
                f"Workflow failed: {e}", type="UnexpectedError"
            ) from e

    async def _run(self, params: WorkflowParams) -> WorkflowResult:
        scrape_activities = ScrapeActivities()
        deploy_activities = DeploymentActivities()

        # Step 1: Resolve site and load its configuration via the multi-site
        # loader. site_key=None preserves backward compat with any persisted
        # schedule that predates this field.
        effective_site_key = params.site_key or DEFAULT_SITE_KEY
        site_config_dict = await workflow.execute_activity(
            scrape_activities.load_site,
            effective_site_key,
            schedule_to_close_timeout=timedelta(seconds=30),
        )

        venue_configs: List[Dict[str, Any]] = site_config_dict["venues"]
        site_timezone = site_config_dict.get("timezone") or DEFAULT_SITE_TIMEZONE

        workflow.logger.info(
            f"Loaded site '{effective_site_key}' with "
            f"{len(venue_configs)} venue configurations"
        )

        # Step 2: Scrape venues in parallel batches. Each venue is isolated:
        # one exhausted activity becomes an error entry, not a lost run.
        max_parallel = max(1, params.max_parallel_scrapes)
        workflow.logger.info(
            f"Scraping venues with max_parallel_scrapes={max_parallel}"
        )

        events: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for start in range(0, len(venue_configs), max_parallel):
            batch = venue_configs[start : start + max_parallel]
            workflow.logger.info(
                f"Launching scrape activities for venues {start + 1}-"
                f"{start + len(batch)} of {len(venue_configs)}"
            )

            batch_results = await asyncio.gather(
                *[
                    self._scrape_venue_isolated(
                        scrape_activities, {**config, "timezone": site_timezone}
                    )
                    for config in batch
                ]
            )

            for result in batch_results:
                events.extend(result.get("events", []))
                error = result.get("error")
                if error:
                    errors.append(error)

        workflow.logger.info(f"Scraped {len(events)} events with {len(errors)} errors")

        if venue_configs and errors and not events:
            raise ApplicationError(
                f"All {len(venue_configs)} venues failed to scrape",
                {"errors": errors},
                type="ScrapeFailed",
            )

        # Step 3: Deploy if requested
        deployed = False
        if params.deploy and events:
            web_data = await workflow.execute_activity(
                deploy_activities.generate_web_data,
                {"events": events, "errors": errors, "site": site_config_dict},
                # generate_web_data includes haiku generation, which calls
                # the Anthropic API and can be slow on self-hosted network
                # paths. Cap any single attempt at 90s so a hung call can't
                # eat the whole budget; give the activity up to 3 minutes
                # total across retries to accommodate transient SDK issues.
                start_to_close_timeout=timedelta(seconds=90),
                schedule_to_close_timeout=timedelta(seconds=180),
            )

            deployed = await workflow.execute_activity(
                deploy_activities.deploy_to_git,
                {"web_data": web_data, "site": site_config_dict},
                schedule_to_close_timeout=timedelta(minutes=2),
            )

            workflow.logger.info(f"Deployment {'successful' if deployed else 'failed'}")
            if not deployed:
                raise ApplicationError(
                    f"Deployment failed for site '{effective_site_key}'",
                    type="DeployFailed",
                )

        return WorkflowResult(
            success=True,
            message=f"Workflow completed successfully. Found {len(events)} events.",
            events_count=len(events),
            errors=[error["message"] for error in errors],
            deployed=deployed,
        )

    @staticmethod
    async def _scrape_venue_isolated(
        scrape_activities: ScrapeActivities, venue_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run one scrape activity, converting exhaustion into an error entry.

        Cancellation is re-raised so a cancelled workflow ends Cancelled rather
        than proceeding to deploy with partial data.
        """
        try:
            return await workflow.execute_activity(
                scrape_activities.scrape_single_venue,
                venue_config,
                start_to_close_timeout=SCRAPE_START_TO_CLOSE,
                schedule_to_close_timeout=SCRAPE_SCHEDULE_TO_CLOSE,
            )
        except ActivityError as e:
            if is_cancelled_exception(e):
                raise
            venue_name = venue_config.get("name", venue_config.get("key", "venue"))
            cause = e.cause if e.cause is not None else e
            workflow.logger.error(f"Scrape activity failed for {venue_name}: {cause}")
            return {
                "events": [],
                "error": {
                    "venue_name": venue_name,
                    "message": f"Scrape activity failed: {cause}",
                    "user_message": f"Failed to fetch information for: {venue_name}",
                },
            }
