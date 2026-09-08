"""FoodTruckWorkflow behaviour against a real local Temporal server.

These tests register name-matched mock activities and run the actual workflow
code end to end, so they exercise Temporal's real failure, timeout, and
cancellation semantics rather than a mocked ``execute_activity``.
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List

import pytest
import pytest_asyncio
from temporalio import activity
from temporalio.client import WorkflowFailureError, WorkflowHistory
from temporalio.exceptions import ApplicationError, CancelledError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from around_the_grounds.temporal.shared import WorkflowParams
from around_the_grounds.temporal.workflows import FoodTruckWorkflow

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "temporal"


def _site(venue_keys: List[str], timezone: str = "America/New_York") -> Dict[str, Any]:
    return {
        "key": "park-slope-music",
        "name": "Park Slope Music",
        "template": "music",
        "timezone": timezone,
        "target_repo": "https://github.com/x/y.git",
        "generate_description": False,
        "deploy_subdir": "",
        "public_url": "",
        "calendar_max_timed_hours": None,
        "venues": [
            {
                "key": key,
                "name": f"Venue {key}",
                "url": f"https://{key}.example",
                "source_type": "html",
                "parser_config": {},
            }
            for key in venue_keys
        ],
    }


def _event(venue_key: str) -> Dict[str, Any]:
    return {
        "venue_key": venue_key,
        "venue_name": f"Venue {venue_key}",
        "title": f"Show at {venue_key}",
        "date": "2026-09-08T00:00:00",
        "start_time": None,
        "end_time": None,
        "description": None,
        "extraction_method": "html",
    }


def _error(venue_key: str) -> Dict[str, str]:
    return {
        "venue_name": f"Venue {venue_key}",
        "message": "boom",
        "user_message": f"Failed to fetch information for: Venue {venue_key}",
    }


class Harness:
    """Builds the mock activity set and records what the workflow sent them."""

    def __init__(self, site: Dict[str, Any], scrape: Callable[[Dict[str, Any]], Any]):
        self.site = site
        self.scrape_inputs: List[Dict[str, Any]] = []
        self.generate_inputs: List[Dict[str, Any]] = []
        self.deploy_inputs: List[Dict[str, Any]] = []
        self.deploy_result = True
        self._scrape = scrape

    def activities(self) -> List[Any]:
        harness = self

        @activity.defn(name="load_site")
        async def load_site(site_key: str) -> Dict[str, Any]:
            return harness.site

        @activity.defn(name="scrape_single_venue")
        async def scrape_single_venue(cfg: Dict[str, Any]) -> Dict[str, Any]:
            harness.scrape_inputs.append(cfg)
            result = harness._scrape(cfg)
            if asyncio.iscoroutine(result):
                result = await result
            return result

        @activity.defn(name="generate_web_data")
        async def generate_web_data(payload: Dict[str, Any]) -> Dict[str, Any]:
            harness.generate_inputs.append(payload)
            return {"events": payload["events"], "total_events": len(payload["events"])}

        @activity.defn(name="deploy_to_git")
        async def deploy_to_git(params: Dict[str, Any]) -> bool:
            harness.deploy_inputs.append(params)
            return harness.deploy_result

        return [load_site, scrape_single_venue, generate_web_data, deploy_to_git]


@pytest_asyncio.fixture
async def env() -> AsyncIterator[WorkflowEnvironment]:
    async with await WorkflowEnvironment.start_local() as environment:
        yield environment


async def _run(
    env: WorkflowEnvironment,
    harness: Harness,
    params: WorkflowParams,
) -> Any:
    task_queue = f"tq-{uuid.uuid4()}"
    async with Worker(
        env.client,
        task_queue=task_queue,
        workflows=[FoodTruckWorkflow],
        activities=harness.activities(),
    ):
        return await env.client.execute_workflow(
            FoodTruckWorkflow.run,
            params,
            id=f"wf-{uuid.uuid4()}",
            task_queue=task_queue,
        )


def _failing(bad_keys: set) -> Callable[[Dict[str, Any]], Dict[str, Any]]:
    def scrape(cfg: Dict[str, Any]) -> Dict[str, Any]:
        if cfg["key"] in bad_keys:
            # non_retryable makes the activity exhaust immediately, standing in
            # for a schedule_to_close timeout without waiting minutes.
            raise ApplicationError("activity exhausted", non_retryable=True)
        return {"events": [_event(cfg["key"])], "error": None}

    return scrape


class TestVenueIsolation:
    async def test_one_exhausted_activity_keeps_other_venues(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["a", "b", "c"]), _failing({"b"}))

        result = await _run(env, harness, WorkflowParams(site_key="park-slope-music"))

        assert result.success is True
        assert result.events_count == 2
        assert len(result.errors) == 1
        assert "Scrape activity failed" in result.errors[0]
        assert "activity exhausted" in result.errors[0]

    async def test_failure_in_earlier_batch_does_not_stop_later_batches(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["a", "b", "c", "d"]), _failing({"a"}))

        result = await _run(
            env,
            harness,
            WorkflowParams(site_key="park-slope-music", max_parallel_scrapes=2),
        )

        assert result.events_count == 3
        # Batches run in order; activities inside a batch start in any order.
        keys = [cfg["key"] for cfg in harness.scrape_inputs]
        assert sorted(keys[:2]) == ["a", "b"]
        assert sorted(keys[2:]) == ["c", "d"]

    async def test_event_order_follows_venue_config_order(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["z", "y", "x"]), _failing(set()))
        harness.deploy_result = True

        await _run(
            env,
            harness,
            WorkflowParams(
                site_key="park-slope-music", deploy=True, max_parallel_scrapes=2
            ),
        )

        sent = [e["venue_key"] for e in harness.generate_inputs[0]["events"]]
        assert sent == ["z", "y", "x"]

    async def test_all_activities_failing_fails_the_workflow(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["a", "b"]), _failing({"a", "b"}))

        with pytest.raises(WorkflowFailureError) as exc_info:
            await _run(
                env, harness, WorkflowParams(site_key="park-slope-music", deploy=True)
            )

        cause = exc_info.value.cause
        assert isinstance(cause, ApplicationError)
        assert cause.type == "ScrapeFailed"
        assert harness.deploy_inputs == []

    async def test_all_venues_reporting_errors_fails_the_workflow(
        self, env: WorkflowEnvironment
    ) -> None:
        """Normal error results (no exception) from every venue are still a failure."""

        def scrape(cfg: Dict[str, Any]) -> Dict[str, Any]:
            return {"events": [], "error": _error(cfg["key"])}

        harness = Harness(_site(["a", "b"]), scrape)

        with pytest.raises(WorkflowFailureError) as exc_info:
            await _run(env, harness, WorkflowParams(site_key="park-slope-music"))

        cause = exc_info.value.cause
        assert isinstance(cause, ApplicationError)
        assert cause.type == "ScrapeFailed"
        assert cause.details[0]["errors"][0]["venue_name"] == "Venue a"

    async def test_empty_schedule_without_errors_is_success(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["a"]), lambda cfg: {"events": [], "error": None})

        result = await _run(
            env, harness, WorkflowParams(site_key="park-slope-music", deploy=True)
        )

        assert result.success is True
        assert result.events_count == 0
        assert result.deployed is False
        assert harness.deploy_inputs == []


class TestDeployOutcome:
    async def test_successful_deploy(self, env: WorkflowEnvironment) -> None:
        harness = Harness(_site(["a"]), _failing(set()))

        result = await _run(
            env, harness, WorkflowParams(site_key="park-slope-music", deploy=True)
        )

        assert result.deployed is True
        assert harness.deploy_inputs[0]["site"]["key"] == "park-slope-music"
        assert harness.generate_inputs[0]["site"]["timezone"] == "America/New_York"

    async def test_failed_deploy_fails_the_workflow(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(_site(["a"]), _failing(set()))
        harness.deploy_result = False

        with pytest.raises(WorkflowFailureError) as exc_info:
            await _run(
                env, harness, WorkflowParams(site_key="park-slope-music", deploy=True)
            )

        cause = exc_info.value.cause
        assert isinstance(cause, ApplicationError)
        assert cause.type == "DeployFailed"


class TestTimezonePropagation:
    async def test_site_timezone_reaches_every_scrape_activity(
        self, env: WorkflowEnvironment
    ) -> None:
        harness = Harness(
            _site(["a", "b"], timezone="America/New_York"), _failing(set())
        )

        await _run(env, harness, WorkflowParams(site_key="park-slope-music"))

        assert [cfg["timezone"] for cfg in harness.scrape_inputs] == [
            "America/New_York",
            "America/New_York",
        ]
        # Venue fields are passed through untouched.
        by_key = {cfg["key"]: cfg for cfg in harness.scrape_inputs}
        assert by_key["a"]["url"] == "https://a.example"

    async def test_default_site_key_when_params_omit_it(
        self, env: WorkflowEnvironment
    ) -> None:
        """Persisted schedules predating site_key must keep resolving to Ballard."""
        seen: List[str] = []
        harness = Harness(_site(["a"]), _failing(set()))

        @activity.defn(name="load_site")
        async def load_site(site_key: str) -> Dict[str, Any]:
            seen.append(site_key)
            return harness.site

        acts = [a for a in harness.activities() if a.__name__ != "load_site"] + [
            load_site
        ]
        task_queue = f"tq-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FoodTruckWorkflow],
            activities=acts,
        ):
            await env.client.execute_workflow(
                FoodTruckWorkflow.run,
                WorkflowParams(),
                id=f"wf-{uuid.uuid4()}",
                task_queue=task_queue,
            )
        assert seen == ["ballard-food-trucks"]


class TestCancellation:
    async def test_cancel_during_scrape_never_deploys(
        self, env: WorkflowEnvironment
    ) -> None:
        started = asyncio.Event()

        async def scrape(cfg: Dict[str, Any]) -> Dict[str, Any]:
            if cfg["key"] == "slow":
                started.set()
                # Heartbeat so cancellation can be delivered to the activity.
                while True:
                    activity.heartbeat()
                    await asyncio.sleep(0.05)
            return {"events": [_event(cfg["key"])], "error": None}

        harness = Harness(_site(["fast", "slow"]), scrape)
        task_queue = f"tq-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=task_queue,
            workflows=[FoodTruckWorkflow],
            activities=harness.activities(),
        ):
            handle = await env.client.start_workflow(
                FoodTruckWorkflow.run,
                WorkflowParams(site_key="park-slope-music", deploy=True),
                id=f"wf-{uuid.uuid4()}",
                task_queue=task_queue,
            )
            await asyncio.wait_for(started.wait(), timeout=10)
            await handle.cancel()

            with pytest.raises(WorkflowFailureError) as exc_info:
                await handle.result()

        assert isinstance(exc_info.value.cause, CancelledError)
        assert harness.generate_inputs == []
        assert harness.deploy_inputs == []


class TestReplayCompatibility:
    """Histories recorded by the pre-isolation workflow must replay on new code."""

    @pytest.mark.parametrize(
        "fixture",
        sorted(p.name for p in FIXTURES.glob("food_truck_workflow_*.json")),
    )
    async def test_pre_change_history_replays(self, fixture: str) -> None:
        with open(FIXTURES / fixture) as f:
            history = json.load(f)

        replayer = Replayer(workflows=[FoodTruckWorkflow])
        await replayer.replay_workflow(WorkflowHistory.from_json(fixture, history))
