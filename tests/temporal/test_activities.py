"""Tests for Temporal activities."""

from datetime import datetime
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from around_the_grounds.temporal.activities import (
    DeploymentActivities,
    ScrapeActivities,
)


@pytest.fixture
def mock_venue_configs() -> List[Dict[str, Any]]:
    """Fixture providing mock brewery configurations."""
    return [
        {
            "key": "test-brewery-1",
            "name": "Test Brewery 1",
            "url": "https://test1.com",
            "parser_config": {"selector": ".event"},
        },
        {
            "key": "test-brewery-2",
            "name": "Test Brewery 2",
            "url": "https://test2.com",
            "parser_config": {"selector": ".truck"},
        },
    ]


@pytest.fixture
def mock_events() -> List[Dict[str, Any]]:
    """Fixture providing mock food truck events (new field names)."""
    return [
        {
            "venue_key": "test-brewery-1",
            "venue_name": "Test Brewery 1",
            "title": "Test Truck 1",
            "date": "2025-07-06T00:00:00",
            "start_time": "2025-07-06T13:00:00",
            "end_time": "2025-07-06T20:00:00",
            "description": "Great food truck",
            "extraction_method": "html",
        },
        {
            "venue_key": "test-brewery-1",
            "venue_name": "Test Brewery 1",
            "title": "AI Truck",
            "date": "2025-07-07T00:00:00",
            "start_time": None,
            "end_time": None,
            "description": None,
            "extraction_method": "ai-vision",
        },
    ]


class TestScrapeActivities:
    """Tests for ScrapeActivities."""

    @pytest.mark.asyncio
    async def test_load_site_returns_serializable_dict(self) -> None:
        """load_site activity returns a flat dict suitable for the activity boundary."""
        activities = ScrapeActivities()

        from around_the_grounds.models import SiteConfig, Venue

        mock_site = SiteConfig(
            key="ballard-food-trucks",
            name="Food Trucks in Ballard",
            template="food-trucks",
            timezone="America/Los_Angeles",
            venues=[
                Venue(
                    key="stoup-ballard",
                    name="Stoup",
                    url="https://stoup.com",
                    source_type="html",
                    parser_config={"selector": ".event"},
                ),
            ],
            target_repo="https://github.com/test/repo.git",
            generate_description=True,
            deploy_subdir="public",
        )

        with patch(
            "around_the_grounds.temporal.activities.load_site_config"
        ) as mock_load:
            mock_load.return_value = mock_site

            result = await activities.load_site("ballard-food-trucks")

        mock_load.assert_called_once_with("ballard-food-trucks")
        assert result["key"] == "ballard-food-trucks"
        assert result["name"] == "Food Trucks in Ballard"
        assert result["template"] == "food-trucks"
        assert result["timezone"] == "America/Los_Angeles"
        assert result["target_repo"] == "https://github.com/test/repo.git"
        assert result["generate_description"] is True
        assert result["deploy_subdir"] == "public"
        assert isinstance(result["venues"], list)
        assert result["venues"][0]["key"] == "stoup-ballard"
        assert result["venues"][0]["source_type"] == "html"
        assert result["venues"][0]["parser_config"]["selector"] == ".event"

    @pytest.mark.asyncio
    async def test_scrape_single_venue_success(
        self, mock_venue_configs: List[Dict[str, Any]]
    ) -> None:
        """Test scraping a single brewery without errors."""
        activities = ScrapeActivities()

        with patch(
            "around_the_grounds.temporal.activities.ScraperCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            from around_the_grounds.models import Event

            mock_event = Event(
                venue_key="test-brewery-1",
                venue_name="Test Brewery 1",
                title="Test Truck 1",
                date=datetime(2025, 7, 6),
                start_time=None,
                end_time=None,
                description=None,
                extraction_method="html",
            )

            mock_coordinator.scrape_one = AsyncMock(return_value=([mock_event], None))

            result = await activities.scrape_single_venue(mock_venue_configs[0])

            assert "events" in result
            assert "error" in result
            assert len(result["events"]) == 1
            assert result["error"] is None

            mock_coordinator_class.assert_called_once_with(max_concurrent=1)
            mock_coordinator.scrape_one.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_scrape_single_venue_with_error(
        self, mock_venue_configs: List[Dict[str, Any]]
    ) -> None:
        """Test scraping a single brewery that returns an error."""
        activities = ScrapeActivities()

        with patch(
            "around_the_grounds.temporal.activities.ScraperCoordinator"
        ) as mock_coordinator_class:
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            from around_the_grounds.models import Venue
            from around_the_grounds.scrapers.coordinator import ScrapingError

            error_brewery = Venue(
                key="test-brewery-1",
                name="Test Brewery 1",
                url="https://test1.com",
                parser_config={},
            )

            mock_error = ScrapingError(
                venue=error_brewery,
                error_type="network_error",
                message="Connection timeout",
            )

            mock_coordinator.scrape_one = AsyncMock(return_value=([], mock_error))

            result = await activities.scrape_single_venue(mock_venue_configs[0])

            assert result["events"] == []
            assert result["error"] is not None
            assert result["error"]["venue_name"] == "Test Brewery 1"
            assert (
                result["error"]["user_message"]
                == "Failed to fetch information for: Test Brewery 1"
            )


class TestDeploymentActivities:
    """Tests for DeploymentActivities."""

    @pytest.mark.asyncio
    async def test_generate_web_data_passes_site_kwarg(
        self, mock_events: List[Dict[str, Any]]
    ) -> None:
        """generate_web_data reconstructs SiteConfig and passes it as site=."""
        activities = DeploymentActivities()

        site_dict = {
            "key": "ballard-food-trucks",
            "name": "Food Trucks in Ballard",
            "template": "food-trucks",
            "timezone": "America/Los_Angeles",
            "target_repo": "https://github.com/steveandroulakis/ballard-food-trucks.git",
            "generate_description": True,
            "deploy_subdir": "public",
            "venues": [
                {
                    "key": "test",
                    "name": "Test",
                    "url": "https://test.com",
                    "source_type": "html",
                    "parser_config": {},
                }
            ],
        }

        with patch(
            "around_the_grounds.temporal.activities.generate_web_data"
        ) as mock_generate:
            mock_generate.return_value = {"events": [], "total_events": 0}

            payload = {
                "events": mock_events,
                "errors": [
                    {
                        "user_message": "Failed to fetch information for brewery: Test Venue 1"
                    }
                ],
                "site": site_dict,
            }

            await activities.generate_web_data(payload)

        mock_generate.assert_called_once()
        call_args = mock_generate.call_args
        reconstructed_events = call_args[0][0]
        error_messages = call_args[0][1]
        passed_site = call_args[1]["site"]

        assert len(reconstructed_events) == 2
        assert reconstructed_events[0].title == "Test Truck 1"
        assert reconstructed_events[1].extraction_method == "ai-vision"
        assert error_messages == [
            "Failed to fetch information for brewery: Test Venue 1"
        ]
        assert passed_site is not None
        assert passed_site.key == "ballard-food-trucks"
        assert passed_site.deploy_subdir == "public"
        assert passed_site.generate_description is True

    @pytest.mark.asyncio
    async def test_generate_web_data_without_site_passes_none(
        self, mock_events: List[Dict[str, Any]]
    ) -> None:
        """If site is omitted (e.g. older payloads), site=None is passed through."""
        activities = DeploymentActivities()

        with patch(
            "around_the_grounds.temporal.activities.generate_web_data"
        ) as mock_generate:
            mock_generate.return_value = {"events": [], "total_events": 0}

            await activities.generate_web_data({"events": mock_events, "errors": []})

        assert mock_generate.call_args[1]["site"] is None

    @pytest.mark.asyncio
    async def test_deploy_to_git_delegates_to_cli_with_site_fields(self) -> None:
        """deploy_to_git reconstructs SiteConfig and delegates to CLI deploy."""
        activities = DeploymentActivities()

        mock_web_data = {"total_events": 1, "events": []}
        site_dict = {
            "key": "ballard-food-trucks",
            "name": "Food Trucks in Ballard",
            "template": "food-trucks",
            "timezone": "America/Los_Angeles",
            "target_repo": "https://github.com/steveandroulakis/ballard-food-trucks.git",
            "generate_description": True,
            "deploy_subdir": "public",
            "venues": [],
        }

        with patch(
            "around_the_grounds.main._deploy_with_github_auth", return_value=True
        ) as mock_deploy:
            params = {"web_data": mock_web_data, "site": site_dict}
            result = await activities.deploy_to_git(params)

        assert result is True
        mock_deploy.assert_called_once_with(
            mock_web_data,
            "https://github.com/steveandroulakis/ballard-food-trucks.git",
            "food-trucks",
            "public",
        )

    @pytest.mark.asyncio
    async def test_deploy_to_git_raises_when_site_missing(self) -> None:
        """deploy_to_git is the new path; payload must carry a site dict."""
        activities = DeploymentActivities()

        with pytest.raises(ValueError, match="requires a 'site' payload field"):
            await activities.deploy_to_git({"web_data": {"total_events": 0}})

    @pytest.mark.asyncio
    async def test_deploy_to_git_propagates_failure(self) -> None:
        """A False return from the CLI deploy raises ValueError up the activity."""
        activities = DeploymentActivities()

        site_dict = {
            "key": "test",
            "name": "Test",
            "template": "food-trucks",
            "timezone": "America/Los_Angeles",
            "target_repo": "https://github.com/test/repo.git",
            "generate_description": False,
            "deploy_subdir": "",
            "venues": [],
        }

        with patch(
            "around_the_grounds.main._deploy_with_github_auth", return_value=False
        ):
            with pytest.raises(ValueError, match="Failed to deploy"):
                await activities.deploy_to_git(
                    {"web_data": {"total_events": 0}, "site": site_dict}
                )
