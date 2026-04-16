"""Integration tests for CLI functionality."""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import AsyncMock, patch

import pytest

from around_the_grounds.main import (
    _deploy_with_github_auth,
    format_events_output,
    main,
    preview_locally,
)
from around_the_grounds.models import Event, Venue
from around_the_grounds.models.site import SiteConfig
from around_the_grounds.scrapers.coordinator import ScrapingError


class TestCLI:
    """Test CLI functionality."""

    @pytest.fixture
    def temp_config_file(
        self, test_site_config: Dict[str, Any]
    ) -> Generator[str, None, None]:
        """Create a temporary SiteConfig-shaped config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_site_config, f)
            temp_path = f.name

        yield temp_path

        Path(temp_path).unlink()

    @pytest.fixture
    def sample_cli_events(self) -> List[Event]:
        """Create sample events for CLI testing."""
        future_date = datetime.now() + timedelta(days=1)
        return [
            Event(
                venue_key="test-brewery",
                venue_name="Test Brewery",
                title="Amazing BBQ Truck",
                date=future_date,
                start_time=future_date.replace(hour=12),
                end_time=future_date.replace(hour=20),
                description="Delicious BBQ all day",
            ),
            Event(
                venue_key="test-brewery-2",
                venue_name="Test Brewery 2",
                title="Taco Supreme",
                date=future_date,
                start_time=future_date.replace(hour=11),
                end_time=future_date.replace(hour=21),
            ),
        ]

    def test_format_events_output_with_events(
        self, sample_cli_events: List[Event]
    ) -> None:
        """Test formatting events for output."""
        output = format_events_output(sample_cli_events)

        assert "Found 2 events:" in output
        assert "Amazing BBQ Truck" in output
        assert "Taco Supreme" in output
        assert "Test Brewery" in output
        assert "🎫" in output  # Event emoji
        assert "📅" in output  # Calendar emoji

    def test_format_events_output_no_events(self) -> None:
        """Test formatting when no events are found."""
        output = format_events_output([])

        assert "No events found" in output

    def test_format_events_output_with_errors(
        self, sample_cli_events: List[Event]
    ) -> None:
        """Test formatting with both events and errors."""
        brewery = Venue("failed-brewery", "Failed Venue", "https://example.com")
        errors = [
            ScrapingError(brewery, "Network Timeout", "Connection timed out"),
            ScrapingError(brewery, "Parser Error", "Failed to parse HTML"),
        ]

        output = format_events_output(sample_cli_events, errors)

        assert "Found 2 events:" in output
        assert "⚠️  Processing Summary:" in output
        assert "✅ 2 events found successfully" in output
        assert "❌ 2 venues failed" in output
        assert "❌ Errors:" in output
        assert (
            "Failed to fetch information for: Failed Venue" in output
        )

    def test_format_events_output_only_errors(self) -> None:
        """Test formatting when only errors occur."""
        brewery = Venue("failed-brewery", "Failed Venue", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Network failed")]

        output = format_events_output([], errors)

        assert "❌ No events found - all venues failed" in output
        assert "❌ Errors:" in output
        assert (
            "Failed to fetch information for: Failed Venue" in output
        )

    def test_format_events_output_instagram_fallback(self) -> None:
        """Test formatting Instagram fallback events."""
        future_date = datetime.now() + timedelta(days=1)
        instagram_event = Event(
            venue_key="test-brewery",
            venue_name="Test Brewery",
            title="Check Instagram @TestBrewery",
            date=future_date,
            description="Food truck schedule not available on website - check Instagram",
        )

        output = format_events_output([instagram_event])

        assert "❌ Check Instagram @TestBrewery" in output
        assert "check Instagram" in output

    def test_format_events_output_ai_generated_name(self) -> None:
        """Test formatting events with AI-generated vendor names."""
        future_date = datetime.now() + timedelta(days=1)
        ai_event = Event(
            venue_key="test-brewery",
            venue_name="Test Brewery",
            title="Georgia's",
            date=future_date,
            start_time=future_date.replace(hour=12),
            end_time=future_date.replace(hour=20),
            description="Greek food",
            extraction_method="ai-vision",
        )
        regular_event = Event(
            venue_key="test-brewery",
            venue_name="Test Brewery",
            title="Taco Supreme",
            date=future_date,
            start_time=future_date.replace(hour=11),
            end_time=future_date.replace(hour=21),
            extraction_method="html",
        )

        output = format_events_output([ai_event, regular_event])

        # AI-generated name should have emoji indicators
        assert "🎫 Georgia's 🖼️🤖 @ Test Brewery" in output
        # Regular name should not have emoji indicators
        assert "🎫 Taco Supreme @ Test Brewery" in output
        # Ensure no AI emojis for regular events
        assert "Taco Supreme 🖼️🤖" not in output

    def test_main_success(
        self,
        temp_config_file: str,
        sample_cli_events: List[Event],
        capsys: Any,
    ) -> None:
        """Test successful main function execution via --config path."""
        with patch(
            "around_the_grounds.main.scrape_site", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = (sample_cli_events, [])

            exit_code = main(["--config", temp_config_file])

            assert exit_code == 0
            captured = capsys.readouterr()
            assert "Around the Grounds" in captured.out
            assert "Found 2 events:" in captured.out

    def test_main_complete_failure(self, temp_config_file: str, capsys: Any) -> None:
        """Test main function with complete failure."""
        brewery = Venue("failed", "Failed", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Failed")]

        with patch(
            "around_the_grounds.main.scrape_site", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = ([], errors)

            exit_code = main(["--config", temp_config_file])

            assert exit_code == 1  # Complete failure
            captured = capsys.readouterr()
            assert "❌ No events found - all venues failed" in captured.out

    def test_main_partial_failure(
        self,
        temp_config_file: str,
        sample_cli_events: List[Event],
        capsys: Any,
    ) -> None:
        """Test main function with partial failure."""
        brewery = Venue("failed", "Failed", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Failed")]

        with patch(
            "around_the_grounds.main.scrape_site", new_callable=AsyncMock
        ) as mock_scrape:
            mock_scrape.return_value = (sample_cli_events, errors)

            exit_code = main(["--config", temp_config_file])

            assert exit_code == 2  # Partial success
            captured = capsys.readouterr()
            assert "Found 2 events:" in captured.out
            assert "⚠️  Processing Summary:" in captured.out

    def test_main_critical_error(self, temp_config_file: str, capsys: Any) -> None:
        """Test main function with critical error."""
        with patch("around_the_grounds.main.asyncio.run") as mock_run:
            mock_run.side_effect = Exception("Critical error occurred")

            exit_code = main(["--config", temp_config_file])

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Critical Error: Critical error occurred" in captured.out

    def test_main_verbose_mode(self, temp_config_file: str, capsys: Any) -> None:
        """Test main function in verbose mode."""
        with patch("around_the_grounds.main.asyncio.run") as mock_run:
            mock_run.side_effect = Exception("Test error")

            exit_code = main(["--config", temp_config_file, "--verbose"])

            assert exit_code == 1
            captured = capsys.readouterr()
            # Should show traceback in verbose mode
            assert "Traceback" in captured.out or "Test error" in captured.out

    def test_main_version_flag(self, capsys: Any) -> None:
        """Test main function with version flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out

    def test_main_help_flag(self, capsys: Any) -> None:
        """Test main function with help flag."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "Track event schedules" in captured.out or "--config" in captured.out
        assert "--config" in captured.out
        assert "--verbose" in captured.out

    def test_main_invalid_config_file(self, capsys: Any) -> None:
        """Test main function with invalid config file."""
        exit_code = main(["--config", "/nonexistent/config.json"])

        assert exit_code == 1
        captured = capsys.readouterr()
        # Either Critical Error: ... or our explicit Config file invalid message
        assert (
            "not found" in captured.out or "Config file invalid" in captured.out
        )

    def test_main_default_site_missing(self, capsys: Any) -> None:
        """Test main function when the default site config is missing."""
        with patch("around_the_grounds.main.load_site_config") as mock_load:
            mock_load.side_effect = FileNotFoundError("Site not found")

            exit_code = main([])

            assert exit_code == 1
            captured = capsys.readouterr()
            assert "Default site" in captured.out

    @pytest.mark.asyncio
    async def test_main_integration_end_to_end(self, temp_config_file: str) -> None:
        """Test end-to-end integration without mocking."""
        # This test uses real components but mocks the network calls
        from aioresponses import aioresponses

        # Mock the network responses for both breweries
        test_html = """
        <html><body>
            <div class="food-truck-entry">
                <h4>Fri 07.05</h4>
                <p>1 — 8pm</p>
                <p>Integration Test Truck</p>
            </div>
        </body></html>
        """

        with aioresponses() as m:
            # Mock responses for both test breweries
            m.get("https://example1.com/food-trucks", status=200, body=test_html)
            m.get("https://example2.com/food-trucks", status=200, body=test_html)

            # Note: This would require actual parser implementations
            # that can handle the test URLs from the config
            # For now, this documents the integration test structure


class TestTemplatePathTraversalGuard:
    """Tests for the path traversal guard in _deploy_with_github_auth and preview_locally."""

    def test_deploy_rejects_traversal_template(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """_deploy_with_github_auth returns False and prints an error for traversal names."""
        (tmp_path / "public_templates").mkdir()

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            result = _deploy_with_github_auth(
                web_data={},
                repository_url="https://github.com/user/repo.git",
                template_dir_name="../escape_target",
            )
        finally:
            os.chdir(original_cwd)

        assert result is False
        captured = capsys.readouterr()
        assert "Template path escapes" in captured.out

    def test_deploy_accepts_valid_template(self, tmp_path: Path, capsys: Any) -> None:
        """_deploy_with_github_auth does not trigger the traversal guard for a valid name."""
        (tmp_path / "public_templates" / "food-trucks").mkdir(parents=True)

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            # GitHub auth will fail (no credentials), but the guard must not fire.
            _deploy_with_github_auth(
                web_data={},
                repository_url="https://github.com/user/repo.git",
                template_dir_name="food-trucks",
            )
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert "Template path escapes" not in captured.out

    def test_preview_rejects_traversal_template(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """preview_locally returns False when the template name escapes public_templates/."""
        (tmp_path / "public_templates").mkdir()

        site = SiteConfig(
            key="test",
            name="Test",
            template="../escape_preview",
            timezone="America/New_York",
            venues=[],
        )

        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)

            async def _run() -> bool:
                with patch(
                    "around_the_grounds.main.generate_web_data",
                    new_callable=AsyncMock,
                ) as mock_gen:
                    mock_gen.return_value = {}
                    return await preview_locally(events=[], site=site)

            result = asyncio.run(_run())
        finally:
            os.chdir(original_cwd)

        # ValueError is caught inside preview_locally; it returns False.
        assert result is False
        captured = capsys.readouterr()
        assert "Template path escapes" in captured.out
