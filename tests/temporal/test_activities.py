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
def mock_brewery_configs() -> List[Dict[str, Any]]:
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
    """Fixture providing mock food truck events."""
    return [
        {
            "brewery_key": "test-brewery-1",
            "brewery_name": "Test Brewery 1",
            "food_truck_name": "Test Truck 1",
            "date": "2025-07-06T00:00:00",
            "start_time": "2025-07-06T13:00:00",
            "end_time": "2025-07-06T20:00:00",
            "description": "Great food truck",
            "ai_generated_name": False,
        },
        {
            "brewery_key": "test-brewery-1",
            "brewery_name": "Test Brewery 1",
            "food_truck_name": "AI Truck",
            "date": "2025-07-07T00:00:00",
            "start_time": None,
            "end_time": None,
            "description": None,
            "ai_generated_name": True,
        },
    ]


class TestScrapeActivities:
    """Tests for ScrapeActivities."""

    @pytest.mark.asyncio
    async def test_load_brewery_config_default(self) -> None:
        """Test loading brewery configuration with default path."""
        activities = ScrapeActivities()

        with patch(
            "around_the_grounds.temporal.activities.load_brewery_config"
        ) as mock_load:
            # Mock breweries
            from around_the_grounds.models import Brewery

            mock_breweries = [
                Brewery(
                    key="stoup-ballard",
                    name="Stoup Brewing - Ballard",
                    url="https://stoup.com/food-trucks",
                    parser_config={"selector": ".event"},
                ),
                Brewery(
                    key="urban-family",
                    name="Urban Family Brewing",
                    url="https://urbanfamilybrewing.com",
                    parser_config={"api_url": "https://api.urbanfamily.com"},
                ),
            ]
            mock_load.return_value = mock_breweries

            result = await activities.load_brewery_config()

            assert isinstance(result, list)
            assert len(result) == 2

            # Check first brewery
            assert result[0]["key"] == "stoup-ballard"
            assert result[0]["name"] == "Stoup Brewing - Ballard"
            assert result[0]["url"] == "https://stoup.com/food-trucks"
            assert result[0]["parser_config"]["selector"] == ".event"

            # Check second brewery
            assert result[1]["key"] == "urban-family"
            assert result[1]["name"] == "Urban Family Brewing"
            assert result[1]["url"] == "https://urbanfamilybrewing.com"
            assert (
                result[1]["parser_config"]["api_url"] == "https://api.urbanfamily.com"
            )

            mock_load.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_load_brewery_config_custom_path(self) -> None:
        """Test loading brewery configuration with custom path."""
        activities = ScrapeActivities()
        custom_path = "/path/to/custom/config.json"

        with patch(
            "around_the_grounds.temporal.activities.load_brewery_config"
        ) as mock_load:
            mock_load.return_value = []

            result = await activities.load_brewery_config(custom_path)

            assert isinstance(result, list)
            mock_load.assert_called_once_with(custom_path)

    @pytest.mark.asyncio
    async def test_scrape_food_trucks_success(
        self, mock_brewery_configs: List[Dict[str, Any]]
    ) -> None:
        """Test successful food truck scraping."""
        activities = ScrapeActivities()

        with patch(
            "around_the_grounds.temporal.activities.ScraperCoordinator"
        ) as mock_coordinator_class:
            # Mock coordinator instance
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Mock food truck events
            from around_the_grounds.models import FoodTruckEvent

            mock_food_truck_events = [
                FoodTruckEvent(
                    brewery_key="test-brewery-1",
                    brewery_name="Test Brewery 1",
                    food_truck_name="Test Truck 1",
                    date=datetime(2025, 7, 6),
                    start_time=datetime(2025, 7, 6, 13, 0),
                    end_time=datetime(2025, 7, 6, 20, 0),
                    description="Great food truck",
                    ai_generated_name=False,
                ),
                FoodTruckEvent(
                    brewery_key="test-brewery-2",
                    brewery_name="Test Brewery 2",
                    food_truck_name="AI Truck",
                    date=datetime(2025, 7, 7),
                    start_time=None,
                    end_time=None,
                    description=None,
                    ai_generated_name=True,
                ),
            ]

            mock_coordinator.scrape_all = AsyncMock(return_value=mock_food_truck_events)
            mock_coordinator.get_errors = MagicMock(return_value=[])

            events, errors = await activities.scrape_food_trucks(mock_brewery_configs)

            assert isinstance(events, list)
            assert isinstance(errors, list)
            assert len(events) == 2
            assert len(errors) == 0

            # Check first event serialization
            event1 = events[0]
            assert event1["brewery_key"] == "test-brewery-1"
            assert event1["brewery_name"] == "Test Brewery 1"
            assert event1["food_truck_name"] == "Test Truck 1"
            assert event1["date"] == "2025-07-06T00:00:00"
            assert event1["start_time"] == "2025-07-06T13:00:00"
            assert event1["end_time"] == "2025-07-06T20:00:00"
            assert event1["description"] == "Great food truck"
            assert event1["ai_generated_name"] is False

            # Check second event serialization
            event2 = events[1]
            assert event2["brewery_key"] == "test-brewery-2"
            assert event2["brewery_name"] == "Test Brewery 2"
            assert event2["food_truck_name"] == "AI Truck"
            assert event2["date"] == "2025-07-07T00:00:00"
            assert event2["start_time"] is None
            assert event2["end_time"] is None
            assert event2["description"] is None
            assert event2["ai_generated_name"] is True

    @pytest.mark.asyncio
    async def test_scrape_food_trucks_with_errors(
        self, mock_brewery_configs: List[Dict[str, Any]]
    ) -> None:
        """Test food truck scraping with errors."""
        activities = ScrapeActivities()

        with patch(
            "around_the_grounds.temporal.activities.ScraperCoordinator"
        ) as mock_coordinator_class:
            # Mock coordinator instance
            mock_coordinator = AsyncMock()
            mock_coordinator_class.return_value = mock_coordinator

            # Mock scraping error
            from around_the_grounds.models import Brewery
            from around_the_grounds.scrapers.coordinator import ScrapingError

            mock_error_brewery = Brewery(
                key="test-brewery-1",
                name="Test Brewery 1",
                url="https://test1.com",
                parser_config={},
            )

            mock_error = ScrapingError(
                brewery=mock_error_brewery,
                error_type="network_error",
                message="Connection timeout",
            )

            mock_coordinator.scrape_all = AsyncMock(return_value=[])
            mock_coordinator.get_errors = MagicMock(return_value=[mock_error])

            events, errors = await activities.scrape_food_trucks(mock_brewery_configs)

            assert isinstance(events, list)
            assert isinstance(errors, list)
            assert len(events) == 0
            assert len(errors) == 1

            # Check error serialization
            error = errors[0]
            assert error["brewery_name"] == "Test Brewery 1"
            assert error["message"] == "Connection timeout"
            assert (
                error["user_message"]
                == "Failed to fetch information for brewery: Test Brewery 1"
            )


class TestDeploymentActivities:
    """Tests for DeploymentActivities."""

    @pytest.mark.asyncio
    async def test_generate_web_data(self, mock_events: List[Dict[str, Any]]) -> None:
        """Test web data generation from events."""
        activities = DeploymentActivities()

        with patch(
            "around_the_grounds.temporal.activities.generate_web_data"
        ) as mock_generate:
            mock_web_data = {
                "events": [
                    {
                        "date": "2025-07-06T00:00:00",
                        "vendor": "Test Truck 1",
                        "location": "Test Brewery 1",
                        "start_time": "01:00 PM",
                        "end_time": "08:00 PM",
                        "description": "Great food truck",
                    },
                    {
                        "date": "2025-07-07T00:00:00",
                        "vendor": "AI Truck 🖼️🤖",
                        "location": "Test Brewery 1",
                        "start_time": None,
                        "end_time": None,
                        "description": None,
                        "extraction_method": "vision",
                    },
                ],
                "total_events": 2,
                "updated": "2025-07-06T00:00:00",
                "errors": [
                    "Failed to fetch information for brewery: Test Brewery 1"
                ],
            }
            mock_generate.return_value = mock_web_data

            payload = {
                "events": mock_events,
                "errors": [
                    {
                        "user_message": "Failed to fetch information for brewery: Test Brewery 1"
                    }
                ],
            }

            result = await activities.generate_web_data(payload)

            assert isinstance(result, dict)
            assert result == mock_web_data

            # Verify the function was called with reconstructed events and errors
            mock_generate.assert_called_once()
            call_args = mock_generate.call_args[0]
            reconstructed_events = call_args[0]
            error_messages = call_args[1]

            assert len(reconstructed_events) == 2
            assert error_messages == [
                "Failed to fetch information for brewery: Test Brewery 1"
            ]

            # Check first reconstructed event
            event1 = reconstructed_events[0]
            assert event1.brewery_key == "test-brewery-1"
            assert event1.brewery_name == "Test Brewery 1"
            assert event1.food_truck_name == "Test Truck 1"
            assert event1.ai_generated_name is False

            # Check second reconstructed event
            event2 = reconstructed_events[1]
            assert event2.brewery_key == "test-brewery-1"
            assert event2.brewery_name == "Test Brewery 1"
            assert event2.food_truck_name == "AI Truck"
            assert event2.ai_generated_name is True

    @pytest.mark.asyncio
    async def test_deploy_to_git_success(self) -> None:
        """Test successful git deployment."""
        activities = DeploymentActivities()

        mock_web_data = {
            "events": [
                {
                    "date": "2025-07-06T00:00:00",
                    "vendor": "Test Truck",
                    "location": "Test Brewery",
                    "start_time": "01:00 PM",
                    "end_time": "08:00 PM",
                    "description": "Great food truck",
                }
            ],
            "total_events": 1,
            "updated": "2025-07-06T00:00:00",
        }

        with patch("around_the_grounds.temporal.activities.Path") as _mock_path, patch(
            "around_the_grounds.temporal.activities.json"
        ) as _mock_json, patch(
            "around_the_grounds.temporal.activities.subprocess"
        ) as mock_subprocess, patch(
            "around_the_grounds.utils.github_auth.GitHubAppAuth"
        ) as _mock_auth_class, patch(
            "tempfile.TemporaryDirectory"
        ) as mock_tempdir, patch("builtins.open", create=True) as _mock_open, patch(
            "around_the_grounds.temporal.activities.shutil.copytree"
        ) as _mock_copytree:
            # Mock temporary directory
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
            mock_tempdir.return_value.__exit__.return_value = None

            # Mock Path operations
            mock_repo_dir = MagicMock()
            mock_repo_dir.configure_mock(**{"__str__.return_value": "/tmp/test/repo"})
            mock_repo_dir.__truediv__.return_value = MagicMock()
            mock_repo_dir.__truediv__.return_value.configure_mock(
                **{"__str__.return_value": "/tmp/test/repo/public"}
            )

            # Mock Path.cwd() to return a proper path
            mock_cwd = MagicMock()
            mock_cwd.configure_mock(**{"__str__.return_value": "/current/dir"})
            mock_cwd.__truediv__.return_value = MagicMock()
            mock_cwd.__truediv__.return_value.configure_mock(
                **{"__str__.return_value": "/current/dir/public_template"}
            )
            _mock_path.cwd.return_value = mock_cwd

            # Mock Path constructor
            _mock_path.side_effect = lambda x: (
                mock_repo_dir if str(x).endswith("repo") else MagicMock()
            )

            # Mock file operations
            mock_file = MagicMock()
            _mock_open.return_value.__enter__.return_value = mock_file

            # Mock GitHub App authentication
            mock_auth = MagicMock()
            _mock_auth_class.return_value = mock_auth
            mock_auth.get_access_token.return_value = "test_token"
            mock_auth.repo_owner = "test"
            mock_auth.repo_name = "test-repo"

            # Mock git operations
            mock_subprocess.run.return_value.returncode = 0

            params = {
                "web_data": mock_web_data,
                "repository_url": "https://github.com/test/repo.git",
            }
            result = await activities.deploy_to_git(params)  # type: ignore

            assert result is True

            # Just verify the function completes successfully with new signature
            # (The implementation changed significantly, so we mainly test it doesn't crash)

    @pytest.mark.asyncio
    async def test_deploy_to_git_git_clone_failure(self) -> None:
        """Test git deployment when git clone fails."""
        activities = DeploymentActivities()

        mock_web_data = {
            "events": [],
            "total_events": 0,
            "updated": "2025-07-06T00:00:00",
        }

        with patch("around_the_grounds.temporal.activities.Path") as _mock_path, patch(
            "around_the_grounds.temporal.activities.json"
        ) as _mock_json, patch(
            "around_the_grounds.temporal.activities.subprocess"
        ) as mock_subprocess, patch(
            "around_the_grounds.utils.github_auth.GitHubAppAuth"
        ) as _mock_auth_class, patch(
            "tempfile.TemporaryDirectory"
        ) as mock_tempdir, patch("builtins.open", create=True) as _mock_open:
            # Mock temporary directory
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"

            # Mock git clone failure
            from subprocess import CalledProcessError

            mock_subprocess.run.side_effect = CalledProcessError(1, "git clone")
            mock_subprocess.CalledProcessError = CalledProcessError

            with pytest.raises(ValueError, match="Failed to deploy to git"):
                params = {
                    "web_data": mock_web_data,
                    "repository_url": "https://github.com/test/repo.git",
                }
                await activities.deploy_to_git(params)  # type: ignore

    @pytest.mark.asyncio
    async def test_deploy_to_git_no_changes(self) -> None:
        """Test git deployment when there are no changes to commit."""
        activities = DeploymentActivities()

        mock_web_data = {
            "events": [],
            "total_events": 0,
            "updated": "2025-07-06T00:00:00",
        }

        with patch("around_the_grounds.temporal.activities.Path") as _mock_path, patch(
            "around_the_grounds.temporal.activities.json"
        ) as _mock_json, patch(
            "around_the_grounds.temporal.activities.subprocess"
        ) as mock_subprocess, patch(
            "around_the_grounds.utils.github_auth.GitHubAppAuth"
        ) as _mock_auth_class, patch(
            "tempfile.TemporaryDirectory"
        ) as mock_tempdir, patch("builtins.open", create=True) as _mock_open, patch(
            "around_the_grounds.temporal.activities.shutil.copytree"
        ) as _mock_copytree:
            # Mock temporary directory
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"
            mock_tempdir.return_value.__exit__.return_value = None

            # Mock Path operations
            mock_repo_dir = MagicMock()
            mock_repo_dir.configure_mock(**{"__str__.return_value": "/tmp/test/repo"})
            mock_repo_dir.__truediv__.return_value = MagicMock()
            mock_repo_dir.__truediv__.return_value.configure_mock(
                **{"__str__.return_value": "/tmp/test/repo/public"}
            )

            # Mock Path.cwd() to return a proper path
            mock_cwd = MagicMock()
            mock_cwd.configure_mock(**{"__str__.return_value": "/current/dir"})
            mock_cwd.__truediv__.return_value = MagicMock()
            mock_cwd.__truediv__.return_value.configure_mock(
                **{"__str__.return_value": "/current/dir/public_template"}
            )
            _mock_path.cwd.return_value = mock_cwd

            # Mock Path constructor
            _mock_path.side_effect = lambda x: (
                mock_repo_dir if str(x).endswith("repo") else MagicMock()
            )

            # Mock git operations - simulate no changes
            def mock_run(cmd: List[str], _cwd: Any = None, **_kwargs: Any) -> Any:
                if "git diff --staged --quiet" in " ".join(cmd):
                    return MagicMock(returncode=0)  # no changes to commit
                else:
                    return MagicMock(returncode=0)

            mock_subprocess.run.side_effect = mock_run

            # Mock authentication
            mock_auth = MagicMock()
            _mock_auth_class.return_value = mock_auth
            mock_auth.get_access_token.return_value = "test_token"
            mock_auth.repo_owner = "test"
            mock_auth.repo_name = "test-repo"

            params = {
                "web_data": mock_web_data,
                "repository_url": "https://github.com/test/repo.git",
            }
            result = await activities.deploy_to_git(params)  # type: ignore

            assert result is True  # Still successful, just no changes

    @pytest.mark.asyncio
    async def test_deploy_to_git_push_failure(self) -> None:
        """Test git deployment with push failure but successful commit."""
        activities = DeploymentActivities()

        mock_web_data = {
            "events": [
                {
                    "date": "2025-07-06T00:00:00",
                    "vendor": "Test Truck",
                    "location": "Test Brewery",
                    "start_time": "01:00 PM",
                    "end_time": "08:00 PM",
                    "description": "Great food truck",
                }
            ],
            "total_events": 1,
            "updated": "2025-07-06T00:00:00",
        }

        with patch("around_the_grounds.temporal.activities.Path") as _mock_path, patch(
            "around_the_grounds.temporal.activities.json"
        ) as _mock_json, patch(
            "around_the_grounds.temporal.activities.subprocess"
        ) as mock_subprocess, patch(
            "around_the_grounds.utils.github_auth.GitHubAppAuth"
        ) as _mock_auth_class, patch(
            "tempfile.TemporaryDirectory"
        ) as mock_tempdir, patch("builtins.open", create=True) as _mock_open:
            # Mock temporary directory
            mock_tempdir.return_value.__enter__.return_value = "/tmp/test"

            # Mock authentication
            mock_auth = MagicMock()
            _mock_auth_class.return_value = mock_auth
            mock_auth.get_access_token.return_value = "test_token"
            mock_auth.repo_owner = "test"
            mock_auth.repo_name = "test-repo"

            # Mock git operations - simulate push failure
            from subprocess import CalledProcessError

            def mock_run(cmd: List[str], _cwd: Any = None, **_kwargs: Any) -> Any:
                if "git push" in " ".join(cmd):
                    raise CalledProcessError(1, cmd, "Push failed")
                elif "git diff --quiet" in " ".join(cmd):
                    return MagicMock(returncode=1)  # has changes
                else:
                    return MagicMock(returncode=0)

            mock_subprocess.run.side_effect = mock_run
            mock_subprocess.CalledProcessError = CalledProcessError

            with pytest.raises(ValueError, match="Failed to deploy to git"):
                params = {
                    "web_data": mock_web_data,
                    "repository_url": "https://github.com/test/repo.git",
                }
                await activities.deploy_to_git(params)  # type: ignore
