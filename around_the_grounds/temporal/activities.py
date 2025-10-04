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
from around_the_grounds.models import Brewery, FoodTruckEvent
from around_the_grounds.scrapers import ScraperCoordinator


class ScrapeActivities:
    """Activities for scraping food truck data."""

    @activity.defn
    async def test_connectivity(self) -> str:
        """Test activity connectivity."""
        return "Activity connectivity test successful"

    @activity.defn
    async def load_brewery_config(
        self, config_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Load brewery configuration and return as serializable data."""
        breweries = load_brewery_config(config_path)
        return [
            {
                "key": b.key,
                "name": b.name,
                "url": b.url,
                "parser_config": b.parser_config,
            }
            for b in breweries
        ]

    @activity.defn
    async def scrape_food_trucks(
        self, brewery_configs: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Scrape food truck data from all breweries."""
        # Convert dicts back to Brewery objects
        breweries = [
            Brewery(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                parser_config=config["parser_config"],
            )
            for config in brewery_configs
        ]

        coordinator = ScraperCoordinator()
        events = await coordinator.scrape_all(breweries)
        errors = coordinator.get_errors()

        # Convert to serializable format
        serialized_events = [
            {
                "brewery_key": event.brewery_key,
                "brewery_name": event.brewery_name,
                "food_truck_name": event.food_truck_name,
                "date": event.date.isoformat(),
                "start_time": (
                    event.start_time.isoformat() if event.start_time else None
                ),
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "description": event.description,
                "ai_generated_name": event.ai_generated_name,
            }
            for event in events
        ]

        serialized_errors = [
            {
                "brewery_name": error.brewery.name,
                "message": error.message,
                "user_message": error.to_user_message(),
            }
            for error in errors
        ]

        return serialized_events, serialized_errors


class DeploymentActivities:
    """Activities for web deployment and git operations."""

    @activity.defn
    async def generate_web_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate web-friendly JSON data from events and errors."""
        events = payload.get("events", [])
        errors = payload.get("errors")

        # Reconstruct events and use existing generate_web_data function
        reconstructed_events = []
        for event_data in events:
            event = FoodTruckEvent(
                brewery_key=event_data["brewery_key"],
                brewery_name=event_data["brewery_name"],
                food_truck_name=event_data["food_truck_name"],
                date=datetime.fromisoformat(event_data["date"]),
                start_time=(
                    datetime.fromisoformat(event_data["start_time"])
                    if event_data["start_time"]
                    else None
                ),
                end_time=(
                    datetime.fromisoformat(event_data["end_time"])
                    if event_data["end_time"]
                    else None
                ),
                description=event_data["description"],
                ai_generated_name=event_data["ai_generated_name"],
            )
            reconstructed_events.append(event)

        error_messages: List[str] = []
        if errors:
            for error in errors:
                if isinstance(error, dict):
                    if "user_message" in error and error["user_message"]:
                        error_messages.append(str(error["user_message"]))
                    elif "brewery_name" in error and error["brewery_name"]:
                        error_messages.append(
                            f"Failed to fetch information for brewery: {error['brewery_name']}"
                        )
                elif isinstance(error, str) and error:
                    error_messages.append(error)

        error_messages = list(dict.fromkeys(error_messages))

        return generate_web_data(reconstructed_events, error_messages)

    @activity.defn
    async def deploy_to_git(self, params: Dict[str, Any]) -> bool:
        """Deploy web data to git repository."""
        import tempfile

        from around_the_grounds.utils.github_auth import GitHubAppAuth

        # Extract parameters
        web_data = params["web_data"]
        repository_url = params["repository_url"]

        try:
            activity.logger.info(
                f"Starting deployment with {web_data.get('total_events', 0)} events"
            )

            # Create temporary directory for git operations
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"

                # Clone the repository
                activity.logger.info(
                    f"Cloning repository {repository_url} to {repo_dir}"
                )
                subprocess.run(
                    ["git", "clone", repository_url, str(repo_dir)],
                    check=True,
                    capture_output=True,
                )

                # Configure git user in the cloned repository
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

                # Copy template files from public_template to cloned repo
                public_template_dir = Path.cwd() / "public_template"
                target_public_dir = repo_dir / "public"

                activity.logger.info(
                    f"Copying template files from {public_template_dir}"
                )
                shutil.copytree(
                    public_template_dir, target_public_dir, dirs_exist_ok=True
                )

                # Write generated web data to cloned repository
                json_path = target_public_dir / "data.json"
                with open(json_path, "w") as f:
                    json.dump(web_data, f, indent=2)

                activity.logger.info(f"Generated web data file: {json_path}")

                # Add all files in public directory
                subprocess.run(
                    ["git", "add", "public/"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Check if there are changes to commit
                result = subprocess.run(
                    ["git", "diff", "--staged", "--quiet"],
                    cwd=repo_dir,
                    capture_output=True,
                )
                if result.returncode == 0:
                    activity.logger.info("No changes to deploy")
                    return True

                # Commit changes
                commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Set up GitHub App authentication and configure remote
                auth = GitHubAppAuth(repository_url)
                access_token = auth.get_access_token()

                authenticated_url = f"https://x-access-token:{access_token}@github.com/{auth.repo_owner}/{auth.repo_name}.git"
                subprocess.run(
                    ["git", "remote", "set-url", "origin", authenticated_url],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

                # Push to origin
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
