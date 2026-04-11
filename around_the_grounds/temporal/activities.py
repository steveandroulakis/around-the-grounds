"""Activity implementations for Temporal workflows."""

import json
import os
import shutil
import subprocess

# Import functions we need (these are safe to import in activities)
import sys
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError
from typing import Any, Dict, List, Optional, Tuple

from temporalio import activity

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from around_the_grounds.main import (
    generate_web_data,
    load_brewery_config,
)
from around_the_grounds.models import Venue, Event
from around_the_grounds.scrapers import ScraperCoordinator
from around_the_grounds.scrapers.coordinator import ScrapingError


class ScrapeActivities:
    """Activities for scraping event data."""

    @staticmethod
    def _serialize_event(event: Event) -> Dict[str, Any]:
        """Convert an event to a JSON-serializable structure."""
        return {
            "venue_key": event.venue_key,
            "venue_name": event.venue_name,
            "title": event.title,
            "date": event.date.isoformat(),
            "start_time": event.start_time.isoformat() if event.start_time else None,
            "end_time": event.end_time.isoformat() if event.end_time else None,
            "description": event.description,
            "extraction_method": event.extraction_method,
        }

    @staticmethod
    def _serialize_error(error: Optional[ScrapingError]) -> Optional[Dict[str, str]]:
        if not error:
            return None
        return {
            "venue_name": error.venue.name,
            "message": error.message,
            "user_message": error.to_user_message(),
        }

    @activity.defn
    async def test_connectivity(self) -> str:
        """Test activity connectivity."""
        return "Activity connectivity test successful"

    @activity.defn
    async def load_brewery_config(
        self, config_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load venue configuration and return as serializable data."""
        venues = load_brewery_config(config_path)
        return [
            {
                "key": v.key,
                "name": v.name,
                "url": v.url,
                "source_type": v.source_type,
                "parser_config": v.parser_config,
            }
            for v in venues
        ]

    @activity.defn
    async def scrape_food_trucks(
        self, venue_configs: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Scrape event data from all venues."""
        # Convert dicts back to Venue objects
        venues = [
            Venue(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                source_type=config.get("source_type", "html"),
                parser_config=config.get("parser_config", {}),
            )
            for config in venue_configs
        ]

        coordinator = ScraperCoordinator()
        events = await coordinator.scrape_all(venues)
        errors = coordinator.get_errors()

        serialized_events = [self._serialize_event(event) for event in events]
        serialized_errors = [
            serialized_error
            for serialized_error in (
                self._serialize_error(error) for error in errors
            )
            if serialized_error
        ]

        return serialized_events, serialized_errors

    @activity.defn
    async def scrape_single_venue(
        self, venue_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Scrape one venue and return serialized events and optional error."""
        venue = Venue(
            key=venue_config["key"],
            name=venue_config["name"],
            url=venue_config["url"],
            source_type=venue_config.get("source_type", "html"),
            parser_config=venue_config.get("parser_config", {}),
        )

        coordinator = ScraperCoordinator(max_concurrent=1)
        events, error = await coordinator.scrape_one(venue)

        return {
            "events": [self._serialize_event(event) for event in events],
            "error": self._serialize_error(error),
        }


class DeploymentActivities:
    """Activities for web deployment and git operations."""

    @activity.defn
    async def generate_web_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate web-friendly JSON data from events and errors."""
        events_data = payload.get("events", [])
        errors = payload.get("errors")

        # Reconstruct events and use existing generate_web_data function
        reconstructed_events = []
        for event_data in events_data:
            event = Event(
                venue_key=event_data.get("venue_key", ""),
                venue_name=event_data.get("venue_name", ""),
                title=event_data.get("title", ""),
                date=datetime.fromisoformat(event_data["date"]),
                start_time=(
                    datetime.fromisoformat(event_data["start_time"])
                    if event_data.get("start_time")
                    else None
                ),
                end_time=(
                    datetime.fromisoformat(event_data["end_time"])
                    if event_data.get("end_time")
                    else None
                ),
                description=event_data.get("description"),
                extraction_method=event_data.get("extraction_method", "html"),
            )
            reconstructed_events.append(event)

        error_messages: List[str] = []
        if errors:
            for error in errors:
                if isinstance(error, dict):
                    if "user_message" in error and error["user_message"]:
                        error_messages.append(str(error["user_message"]))
                    elif "venue_name" in error and error["venue_name"]:
                        error_messages.append(
                            f"Failed to fetch information for: {error['venue_name']}"
                        )
                elif isinstance(error, str) and error:
                    error_messages.append(error)

        error_messages = list(dict.fromkeys(error_messages))

        return await generate_web_data(reconstructed_events, error_messages)

    @activity.defn
    async def deploy_to_git(self, params: Dict[str, Any]) -> bool:
        """Deploy web data to git repository."""
        import tempfile

        from around_the_grounds.utils.github_auth import GitHubAppAuth

        # Extract parameters
        web_data = params["web_data"]
        repository_url = params["repository_url"]
        template_dir_name = params.get("template", "food-trucks")

        try:
            activity.logger.info(
                f"Starting deployment with {web_data.get('total_events', 0)} events"
            )

            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"

                activity.logger.info(
                    f"Cloning repository {repository_url} to {repo_dir}"
                )
                subprocess.run(
                    ["git", "clone", repository_url, str(repo_dir)],
                    check=True,
                    capture_output=True,
                )

                subprocess.run(
                    ["git", "config", "user.email", "steve.androulakis@gmail.com"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "config", "user.name", "Steve Androulakis"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Try new multi-template path first, fall back to legacy
                public_templates_dir = (
                    Path.cwd() / "public_templates" / template_dir_name
                )
                if not public_templates_dir.exists():
                    public_templates_dir = Path.cwd() / "public_template"

                target_public_dir = repo_dir / "public"

                activity.logger.info(
                    f"Copying template files from {public_templates_dir}"
                )
                shutil.copytree(
                    public_templates_dir, target_public_dir, dirs_exist_ok=True
                )

                json_path = target_public_dir / "data.json"
                with open(json_path, "w") as f:
                    json.dump(web_data, f, indent=2)

                activity.logger.info(f"Generated web data file: {json_path}")

                subprocess.run(
                    ["git", "add", "public/"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                result = subprocess.run(
                    ["git", "diff", "--staged", "--quiet"],
                    cwd=repo_dir,
                    capture_output=True,
                )
                if result.returncode == 0:
                    activity.logger.info("No changes to deploy")
                    return True

                site_name = web_data.get("site_name", "Events")
                commit_msg = f"📅 Update {site_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                auth = GitHubAppAuth(repository_url)
                access_token = auth.get_access_token()

                authenticated_url = f"https://x-access-token:{access_token}@github.com/{auth.repo_owner}/{auth.repo_name}.git"
                subprocess.run(
                    ["git", "remote", "set-url", "origin", authenticated_url],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                subprocess.run(
                    ["git", "push", "origin", "main"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )
                activity.logger.info("Deployed to git! Changes will be live shortly.")

                return True

        except CalledProcessError as e:
            error_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
            activity.logger.error(f"Git operation failed: {error_msg}")
            raise ValueError(f"Failed to deploy to git: {error_msg}")
        except Exception as e:
            activity.logger.error(f"Error during deployment: {e}")
            raise ValueError(f"Failed to deploy to git: {e}")
