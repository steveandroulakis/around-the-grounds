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
        assert "Failed to fetch information for: Failed Venue" in output

    def test_format_events_output_only_errors(self) -> None:
        """Test formatting when only errors occur."""
        brewery = Venue("failed-brewery", "Failed Venue", "https://example.com")
        errors = [ScrapingError(brewery, "Network Error", "Network failed")]

        output = format_events_output([], errors)

        assert "❌ No events found - all venues failed" in output
        assert "❌ Errors:" in output
        assert "Failed to fetch information for: Failed Venue" in output

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
        assert "not found" in captured.out or "Config file invalid" in captured.out

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


class TestCalendarFeedOutput:
    """The .ics feed is written alongside data.json by every output path."""

    @staticmethod
    def _web_data() -> Dict[str, Any]:
        return {
            "site_key": "test-site",
            "site_name": "Test Site",
            "timezone": "America/Los_Angeles",
            "total_events": 1,
            "events": [
                {
                    "date": "2026-08-13T00:00:00",
                    "title": "Woodshop BBQ",
                    "venue": "Stoup Brewing",
                    "venue_key": "stoup-ballard",
                    "venue_url": "https://stoupbrewing.com",
                    "start_iso": "2026-08-13T17:00:00",
                    "end_iso": "2026-08-13T21:00:00",
                    "extraction_method": "html",
                }
            ],
            "errors": [],
            "haiku": None,
        }

    def _run_preview(self, tmp_path: Path, web_data: Dict[str, Any]) -> bool:
        (tmp_path / "public_templates" / "food-trucks").mkdir(
            parents=True, exist_ok=True
        )
        (tmp_path / "public_templates" / "food-trucks" / "index.html").write_text(
            "<h1>hi</h1>"
        )

        site = SiteConfig(
            key="test-site",
            name="Test Site",
            template="food-trucks",
            timezone="America/Los_Angeles",
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
                    mock_gen.return_value = web_data
                    return await preview_locally(events=[], site=site)

            return asyncio.run(_run())
        finally:
            os.chdir(original_cwd)

    def test_preview_writes_events_ics_next_to_data_json(self, tmp_path: Path) -> None:
        result = self._run_preview(tmp_path, self._web_data())

        assert result is True
        assert (tmp_path / "public" / "data.json").exists()

        ics_path = tmp_path / "public" / "events.ics"
        assert ics_path.exists()

        raw = ics_path.read_bytes()
        assert raw.startswith(b"BEGIN:VCALENDAR")
        assert b"SUMMARY:Woodshop BBQ\r\n" in raw

    def test_preview_feed_is_byte_stable_across_runs(self, tmp_path: Path) -> None:
        """Unchanged data must produce an identical feed, or every deploy commits."""
        web_data = self._web_data()

        self._run_preview(tmp_path, web_data)
        first = (tmp_path / "public" / "events.ics").read_bytes()

        self._run_preview(tmp_path, web_data)
        second = (tmp_path / "public" / "events.ics").read_bytes()

        assert first == second

    def test_preview_survives_calendar_generation_failure(
        self, tmp_path: Path, capsys: Any
    ) -> None:
        """A broken feed must degrade gracefully, not fail the preview."""
        with patch(
            "around_the_grounds.main.build_ics", side_effect=RuntimeError("boom")
        ):
            result = self._run_preview(tmp_path, self._web_data())

        assert result is True
        assert (tmp_path / "public" / "data.json").exists()
        assert not (tmp_path / "public" / "events.ics").exists()

        captured = capsys.readouterr()
        assert "Skipped calendar feed generation" in captured.out


class TestExitCodes:
    """Exit-code contract consumed by Cloud Run Jobs: 1 failure, 2 partial, 0 clean."""

    @staticmethod
    def _site(key: str) -> SiteConfig:
        return SiteConfig(
            key=key, name=key, template="music", timezone="America/New_York", venues=[]
        )

    @staticmethod
    def _events() -> List[Event]:
        d = datetime.now() + timedelta(days=1)
        return [Event(venue_key="v", venue_name="V", title="T", date=d)]

    @staticmethod
    def _errors() -> List[ScrapingError]:
        return [ScrapingError(Venue("f", "F", "https://f"), "Network Error", "x")]

    def _run(self, argv: List[str], scrape_results: List[Any], **patches: Any) -> int:
        sites = [self._site(f"site-{i}") for i in range(len(scrape_results))]
        with patch("around_the_grounds.main.load_all_sites", return_value=sites), patch(
            "around_the_grounds.main.load_site_config", return_value=sites[0]
        ), patch(
            "around_the_grounds.main.scrape_site",
            new_callable=AsyncMock,
            side_effect=scrape_results,
        ), patch(
            "around_the_grounds.main.deploy_to_web",
            new_callable=AsyncMock,
            return_value=patches.get("deploy", True),
        ) as mock_deploy, patch(
            "around_the_grounds.main.preview_locally",
            new_callable=AsyncMock,
            return_value=patches.get("preview", True),
        ) as mock_preview:
            code = main(argv)
        self.deploy_calls = mock_deploy.await_count
        self.preview_calls = mock_preview.await_count
        return code

    def test_deploy_failure_after_successful_scrape_is_exit_1(self) -> None:
        assert self._run(["--deploy"], [(self._events(), [])], deploy=False) == 1

    def test_preview_failure_after_successful_scrape_is_exit_1(self) -> None:
        assert self._run(["--preview"], [(self._events(), [])], preview=False) == 1

    def test_successful_deploy_is_exit_0(self) -> None:
        assert self._run(["--deploy"], [(self._events(), [])]) == 0
        assert self.deploy_calls == 1

    def test_partial_scrape_with_successful_deploy_is_exit_2(self) -> None:
        assert self._run(["--deploy"], [(self._events(), self._errors())]) == 2

    def test_multi_site_complete_failure_first_then_partial_is_exit_1(self) -> None:
        results = [([], self._errors()), (self._events(), self._errors())]
        assert self._run(["--site", "all"], results) == 1

    def test_multi_site_partial_first_then_complete_failure_is_exit_1(self) -> None:
        results = [(self._events(), self._errors()), ([], self._errors())]
        assert self._run(["--site", "all"], results) == 1

    def test_multi_site_later_site_still_deploys_after_earlier_failure(self) -> None:
        results = [([], self._errors()), (self._events(), [])]
        assert self._run(["--site", "all", "--deploy"], results) == 1
        # The failed site has nothing to publish; the healthy one still deploys.
        assert self.deploy_calls == 1

    def test_deploy_skipped_when_no_events_and_no_errors(self, capsys: Any) -> None:
        assert self._run(["--deploy"], [([], [])]) == 0
        assert self.deploy_calls == 0
        assert "Skipping deploy" in capsys.readouterr().out


class TestDeploySubdirGuard:
    """deploy_subdir is validated before any token is minted or file written."""

    @pytest.mark.parametrize(
        "bad",
        [
            "../outside",
            "public/../../outside",
            "/outside",
            "\\outside",
            "C:\\outside",
            "C:/outside",
            ".",
            "./",
            ".git",
            "public/.git",
            ".GIT/objects",
        ],
    )
    def test_invalid_subdir_rejected_before_auth(
        self, tmp_path: Path, bad: str, capsys: Any
    ) -> None:
        from around_the_grounds.main import _validate_deploy_subdir

        with pytest.raises(ValueError):
            _validate_deploy_subdir(bad)

        (tmp_path / "public_templates" / "food-trucks").mkdir(parents=True)
        original_cwd = Path.cwd()
        try:
            os.chdir(tmp_path)
            with patch(
                "around_the_grounds.main._authenticated_repo_url"
            ) as mock_auth, patch("around_the_grounds.main.subprocess.run") as mock_run:
                ok = _deploy_with_github_auth(
                    web_data={},
                    repository_url="https://github.com/user/repo.git",
                    template_dir_name="food-trucks",
                    deploy_subdir=bad,
                )
        finally:
            os.chdir(original_cwd)

        assert ok is False
        mock_auth.assert_not_called()
        mock_run.assert_not_called()
        assert "deploy_subdir" in capsys.readouterr().out

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("", ""),
            ("public", "public"),
            ("public/", "public"),
            ("./public/", "public"),
            ("site/public", "site/public"),
            ("site[1]", "site[1]"),
            ("site\\public", "site/public"),
        ],
    )
    def test_valid_subdir_normalized(self, raw: str, expected: str) -> None:
        from around_the_grounds.main import _validate_deploy_subdir

        assert _validate_deploy_subdir(raw) == expected


def _git(*args: str, cwd: Path) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


class TestDeployAgainstLocalGit:
    """Exercise the real Git commands against a temporary bare repository."""

    @pytest.fixture
    def bare_repo(self, tmp_path: Path) -> Path:
        """Bare repo whose main branch has root files plus stale public/ content."""
        bare = tmp_path / "target.git"
        bare.mkdir()
        _git("init", "--bare", cwd=bare)
        _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)

        seed = tmp_path / "seed"
        _git("clone", str(bare), str(seed), cwd=tmp_path)
        _git("config", "user.email", "seed@example.com", cwd=seed)
        _git("config", "user.name", "Seed", cwd=seed)
        (seed / "README.md").write_text("keep me\n")
        (seed / "vercel.json").write_text("{}\n")
        (seed / "public").mkdir()
        (seed / "public" / "stale.txt").write_text("old\n")
        (seed / "site[1]").mkdir()
        (seed / "site[1]" / "old.txt").write_text("old\n")
        (seed / "site1").mkdir()
        (seed / "site1" / "unrelated.txt").write_text("unrelated\n")
        _git("add", ".", cwd=seed)
        _git("commit", "-q", "-m", "seed", cwd=seed)
        _git("push", "-q", "origin", "HEAD:main", cwd=seed)
        return bare

    @pytest.fixture
    def workdir(self, tmp_path: Path) -> Generator[Path, None, None]:
        (tmp_path / "public_templates" / "food-trucks").mkdir(parents=True)
        (tmp_path / "public_templates" / "food-trucks" / "index.html").write_text(
            "<h1>site</h1>"
        )
        original_cwd = Path.cwd()
        os.chdir(tmp_path)
        try:
            yield tmp_path
        finally:
            os.chdir(original_cwd)

    @staticmethod
    def _web_data() -> Dict[str, Any]:
        return {
            "site_key": "test-site",
            "site_name": "Test Site",
            "timezone": "America/Los_Angeles",
            "total_events": 1,
            "events": [
                {
                    "date": "2026-08-13T00:00:00",
                    "title": "Woodshop BBQ",
                    "venue": "Stoup Brewing",
                    "venue_key": "stoup-ballard",
                    "start_iso": "2026-08-13T17:00:00",
                    "end_iso": "2026-08-13T21:00:00",
                    "extraction_method": "html",
                }
            ],
            "errors": [],
            "haiku": None,
        }

    def _deploy(self, bare: Path, subdir: str, web_data: Dict[str, Any]) -> bool:
        with patch(
            "around_the_grounds.main._authenticated_repo_url", return_value=str(bare)
        ):
            return _deploy_with_github_auth(
                web_data=web_data,
                repository_url="https://github.com/user/repo.git",
                template_dir_name="food-trucks",
                deploy_subdir=subdir,
            )

    @staticmethod
    def _tree(bare: Path) -> List[str]:
        return _git("ls-tree", "-r", "--name-only", "main", cwd=bare).splitlines()

    @staticmethod
    def _commits(bare: Path) -> int:
        return int(_git("rev-list", "--count", "main", cwd=bare))

    def test_subdir_mode_preserves_root_files_and_is_idempotent(
        self, bare_repo: Path, workdir: Path, capsys: Any
    ) -> None:
        before = self._commits(bare_repo)

        assert self._deploy(bare_repo, "public", self._web_data()) is True

        tree = self._tree(bare_repo)
        assert "README.md" in tree and "vercel.json" in tree
        assert "public/index.html" in tree
        assert "public/data.json" in tree
        assert "public/events.ics" in tree
        assert "public/stale.txt" in tree  # scoped add never deletes
        assert self._commits(bare_repo) == before + 1

        # Same data again: no new commit.
        assert self._deploy(bare_repo, "public", self._web_data()) is True
        assert self._commits(bare_repo) == before + 1
        assert "No changes to deploy" in capsys.readouterr().out

    def test_subdir_with_glob_characters_is_staged_literally(
        self, bare_repo: Path, workdir: Path
    ) -> None:
        # Also drop an untracked file into "site1/" via a template copy? No:
        # the template is only copied into the deploy subdir. Instead verify
        # that "site[1]" (which as a glob would match "site1") stages only
        # its own directory.
        assert self._deploy(bare_repo, "site[1]", self._web_data()) is True

        tree = self._tree(bare_repo)
        assert "site[1]/index.html" in tree
        assert "site[1]/data.json" in tree
        assert "site1/unrelated.txt" in tree
        assert "site1/index.html" not in tree

    def test_root_mode_replaces_repo_contents(
        self, bare_repo: Path, workdir: Path
    ) -> None:
        assert self._deploy(bare_repo, "", self._web_data()) is True

        tree = self._tree(bare_repo)
        assert "index.html" in tree and "data.json" in tree and "events.ics" in tree
        assert "README.md" not in tree
        assert self._commits(bare_repo) == 1

    def test_subdir_symlink_escaping_repo_is_rejected(
        self, bare_repo: Path, workdir: Path, tmp_path: Path, capsys: Any
    ) -> None:
        """A symlink committed to the target repo cannot redirect writes outside it."""
        outside = tmp_path / "outside"
        outside.mkdir()
        seed = tmp_path / "seed"
        os.symlink(outside, seed / "linked")
        _git("add", "linked", cwd=seed)
        _git("commit", "-q", "-m", "add symlink", cwd=seed)
        _git("push", "-q", "origin", "HEAD:main", cwd=seed)

        assert self._deploy(bare_repo, "linked", self._web_data()) is False
        assert list(outside.iterdir()) == []
        assert "outside the repository" in capsys.readouterr().out
