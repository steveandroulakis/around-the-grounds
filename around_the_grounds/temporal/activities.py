"""Activity implementations for Temporal workflows."""

import asyncio
import os

# Import functions we need (these are safe to import in activities)
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from temporalio import activity

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from around_the_grounds.config.loader import load_site_config
from around_the_grounds.main import generate_web_data
from around_the_grounds.models import Event, SiteConfig, Venue
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
    async def load_site(self, site_key: str) -> Dict[str, Any]:
        """Load a site config and return a JSON-serializable dict.

        Sent across the activity boundary as plain dict to keep the existing
        payload pattern (every other activity uses dict payloads). Reconstructed
        into a SiteConfig inside the deploy/generate activities.
        """
        site = load_site_config(site_key)
        return {
            "key": site.key,
            "name": site.name,
            "template": site.template,
            "timezone": site.timezone,
            "target_repo": site.target_repo,
            "generate_description": site.generate_description,
            "deploy_subdir": site.deploy_subdir,
            "public_url": site.public_url,
            "venues": [
                {
                    "key": v.key,
                    "name": v.name,
                    "url": v.url,
                    "source_type": v.source_type,
                    "parser_config": v.parser_config,
                }
                for v in site.venues
            ],
        }

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


def _site_from_dict(site_dict: Dict[str, Any]) -> SiteConfig:
    """Reconstruct a SiteConfig from the dict produced by load_site."""
    return SiteConfig(
        key=site_dict["key"],
        name=site_dict["name"],
        template=site_dict["template"],
        timezone=site_dict["timezone"],
        venues=[
            Venue(
                key=v["key"],
                name=v["name"],
                url=v["url"],
                source_type=v.get("source_type", "html"),
                parser_config=v.get("parser_config", {}),
            )
            for v in site_dict.get("venues", [])
        ],
        target_repo=site_dict.get("target_repo", ""),
        generate_description=site_dict.get("generate_description", True),
        deploy_subdir=site_dict.get("deploy_subdir", ""),
        public_url=site_dict.get("public_url", ""),
    )


class DeploymentActivities:
    """Activities for web deployment and git operations."""

    @activity.defn
    async def generate_web_data(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate web-friendly JSON data from events and errors.

        Delegates to the CLI's generate_web_data so the site-aware code paths
        (haiku gating by SiteConfig.generate_description, real site_name /
        site_key / timezone, ai-vision shim) light up identically to the CLI.
        """
        events_data = payload.get("events", [])
        errors = payload.get("errors")
        site_dict = payload.get("site")

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

        site = _site_from_dict(site_dict) if site_dict else None
        return await generate_web_data(
            reconstructed_events, error_messages, site=site
        )

    @activity.defn
    async def deploy_to_git(self, params: Dict[str, Any]) -> bool:
        """Deploy web data to git repository.

        Delegates to main.py:_deploy_with_github_auth — the single source of
        truth for deploy git logic. That function already handles both
        deploy_subdir modes (root-mode init+force-push and subdir-mode
        clone+scoped-add+push), the no-op short-circuit, the bot identity, and
        the authenticated clone URL.
        """
        # Local import to avoid any chance of a module-load circular import
        # when the worker boots and registers activities.
        from around_the_grounds.main import _deploy_with_github_auth

        web_data = params["web_data"]
        site_dict = params.get("site")

        if not site_dict:
            raise ValueError(
                "deploy_to_git requires a 'site' payload field. The workflow "
                "should have loaded it via the load_site activity."
            )

        site = _site_from_dict(site_dict)

        activity.logger.info(
            f"Starting deployment for site '{site.key}' "
            f"({web_data.get('total_events', 0)} events) "
            f"to {site.target_repo} (deploy_subdir={site.deploy_subdir!r})"
        )

        try:
            # _deploy_with_github_auth is sync and uses blocking subprocess.run.
            # Hand it to the executor so the asyncio loop in this activity stays
            # responsive (the activity itself is registered against the worker's
            # ThreadPoolExecutor; this is belt-and-braces).
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None,
                _deploy_with_github_auth,
                web_data,
                site.target_repo,
                site.template,
                site.deploy_subdir,
            )

            if success:
                activity.logger.info(
                    f"Deployed site '{site.key}' to {site.target_repo}"
                )
            else:
                activity.logger.error(
                    f"Deployment of site '{site.key}' returned False"
                )
                raise ValueError(
                    f"Failed to deploy site '{site.key}' to {site.target_repo}"
                )

            return success

        except Exception as e:
            activity.logger.error(f"Error during deployment: {e}")
            raise ValueError(f"Failed to deploy to git: {e}")
