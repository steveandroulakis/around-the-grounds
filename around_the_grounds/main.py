"""Main entry point for ground-events CLI."""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv(override=True)
except ImportError:
    # dotenv is optional, fall back to os.environ
    pass

from .config.settings import get_git_repository_url
from .config.site_loader import SiteConfigLoader
from .models import Brewery, FoodTruckEvent, SiteConfig, EventSource, Event
from .scrapers import ScraperCoordinator
from .utils.timezone_utils import format_time_with_timezone


def load_brewery_config(config_path: Optional[str] = None) -> List[Brewery]:
    """Load brewery configuration from JSON file (legacy function for backwards compatibility)."""
    if config_path is None:
        config_path_obj = Path(__file__).parent / "config" / "breweries.json"
    else:
        config_path_obj = Path(config_path)

    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path_obj}")

    with open(config_path_obj, "r") as f:
        config = json.load(f)

    breweries = []
    for brewery_data in config.get("breweries", []):
        brewery = Brewery(
            key=brewery_data["key"],
            name=brewery_data["name"],
            url=brewery_data["url"],
            parser_config=brewery_data.get("parser_config", {}),
        )
        breweries.append(brewery)

    return breweries


def load_site_config(site_name: Optional[str] = None) -> SiteConfig:
    """Load site configuration from YAML file with fallback to legacy JSON."""
    site_loader = SiteConfigLoader()

    if site_name is None:
        # Default to ballard-food-trucks for backwards compatibility
        site_name = "ballard-food-trucks"

    try:
        return site_loader.load_site_config(site_name)
    except FileNotFoundError:
        # Fallback: if no YAML config exists, try to convert from legacy JSON
        if site_name == "ballard-food-trucks":
            print("ℹ️  YAML configuration not found, using legacy JSON configuration")
            return convert_legacy_config_to_site_config()
        else:
            raise


def convert_legacy_config_to_site_config() -> SiteConfig:
    """Convert legacy breweries.json to SiteConfig format."""
    breweries = load_brewery_config()

    # Convert breweries to event sources
    sources = []
    for brewery in breweries:
        # Map legacy brewery keys to technology-based parser types
        parser_type_mapping = {
            "stoup-ballard": "html_selectors",
            "yonder-balebreaker": "squarespace_calendar",
            "obec-brewing": "regex_text",
            "urban-family": "hivey_api",
            "wheelie-pop": "text_search_html",
            "chucks-greenwood": "google_sheets_csv",
            "salehs-corner": "seattle_food_truck_api",
        }

        parser_type = parser_type_mapping.get(brewery.key, "html_selectors")

        source = EventSource(
            key=brewery.key,
            name=brewery.name,
            url=brewery.url,
            parser_type=parser_type,
            parser_config=brewery.parser_config
        )
        sources.append(source)

    # Create site config with legacy values
    return SiteConfig(
        name="Food Trucks in Ballard",
        template_type="food_events",
        website_title="Food Trucks in Ballard",
        repository_url="https://github.com/steveandroulakis/ballard-food-trucks",
        description="Daily food truck schedules at Ballard breweries and venues",
        sources=sources,
        event_category="food"
    )


def convert_site_to_breweries(site_config: SiteConfig) -> List[Brewery]:
    """Convert SiteConfig to legacy Brewery format for backwards compatibility."""
    breweries = []
    for source in site_config.sources:
        brewery = Brewery(
            key=source.key,
            name=source.name,
            url=source.url,
            parser_config=source.parser_config
        )
        breweries.append(brewery)
    return breweries


def convert_events_to_food_truck_events(events: List[Event]) -> List[FoodTruckEvent]:
    """Convert Event objects to legacy FoodTruckEvent format."""
    food_truck_events = []
    for event in events:
        food_truck_event = FoodTruckEvent(
            brewery_key=event.source_key,
            brewery_name=event.source_name,
            food_truck_name=event.event_name,
            date=event.date,
            start_time=event.start_time,
            end_time=event.end_time,
            description=event.description,
            ai_generated_name=event.ai_generated_name
        )
        food_truck_events.append(food_truck_event)
    return food_truck_events


def format_events_output(
    events: List[FoodTruckEvent], errors: Optional[List] = None
) -> str:
    """Format events and errors for display."""
    output = []

    # Show events
    if events:
        output.append(f"Found {len(events)} food truck events:")
        output.append("")

        current_date = None
        for event in events:
            event_date = event.date.strftime("%A, %B %d, %Y")

            if current_date != event_date:
                if current_date is not None:
                    output.append("")
                output.append(f"📅 {event_date}")
                current_date = event_date

            time_str = ""
            if event.start_time:
                time_str = f" {event.start_time.strftime('%I:%M %p')}"
                if event.end_time:
                    time_str += f" - {event.end_time.strftime('%I:%M %p')}"

            # Check if this is an error event (fallback)
            if "Check Instagram" in event.food_truck_name or "check Instagram" in (
                event.description or ""
            ):
                output.append(
                    f"  ❌ {event.food_truck_name} @ {event.brewery_name}{time_str}"
                )
                if event.description:
                    output.append(f"     {event.description}")
            else:
                # Add AI vision indicator for AI-generated names
                if event.ai_generated_name:
                    output.append(
                        f"  🚚 {event.food_truck_name} 🖼️🤖 @ {event.brewery_name}{time_str}"
                    )
                else:
                    output.append(
                        f"  🚚 {event.food_truck_name} @ {event.brewery_name}{time_str}"
                    )
                if event.description:
                    output.append(f"     {event.description}")

    # Show errors
    if errors:
        if events:
            output.append("")
            output.append("⚠️  Processing Summary:")
            output.append(f"✅ {len(events)} events found successfully")
            output.append(f"❌ {len(errors)} breweries failed")
        else:
            output.append("❌ No events found - all breweries failed")

        output.append("")
        output.append("❌ Errors:")
        for error in errors:
            output.append(f"  • {error.brewery.name}: {error.message}")

    if not events and not errors:
        output.append("No food truck events found for the next 7 days.")

    return "\n".join(output)


def generate_web_data(events: List[FoodTruckEvent]) -> dict:
    """Generate web-friendly JSON data from events with Pacific timezone information."""
    web_events = []

    for event in events:
        # Convert event to web format with Pacific timezone indicators
        web_event = {
            "date": event.date.isoformat(),
            "vendor": event.food_truck_name,
            "location": event.brewery_name,
            # Format times with Pacific timezone indicators
            "start_time": (
                format_time_with_timezone(event.start_time, include_timezone=True)
                if event.start_time
                else None
            ),
            "end_time": (
                format_time_with_timezone(event.end_time, include_timezone=True)
                if event.end_time
                else None
            ),
            # Also include raw time strings without timezone for backward compatibility
            "start_time_raw": (
                event.start_time.strftime("%I:%M %p").lstrip("0")
                if event.start_time
                else None
            ),
            "end_time_raw": (
                event.end_time.strftime("%I:%M %p").lstrip("0")
                if event.end_time
                else None
            ),
            "description": event.description,
            "timezone": "PT",  # Explicit timezone indicator
        }

        # Add AI extraction indicator
        if event.ai_generated_name:
            web_event["extraction_method"] = "vision"
            web_event["vendor"] = f"{event.food_truck_name} 🖼️🤖"

        web_events.append(web_event)

    return {
        "events": web_events,
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_events": len(web_events),
        "timezone": "PT",  # Global timezone indicator
        "timezone_note": "All event times are in Pacific Time (PT), which includes both PST and PDT depending on the date.",
    }


def deploy_to_web(
    events: List[FoodTruckEvent], git_repo_url: Optional[str] = None
) -> bool:
    """Generate web data and deploy to Vercel via git."""
    try:
        # Get repository URL with fallback chain
        repository_url = get_git_repository_url(git_repo_url)

        # Generate web data
        web_data = generate_web_data(events)

        print(f"✅ Generated web data: {len(events)} events")
        print(f"📍 Target repository: {repository_url}")

        # Use GitHub App authentication for deployment (like Temporal workflow)
        return _deploy_with_github_auth(web_data, repository_url)

    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
        return False


def _deploy_with_github_auth(web_data: dict, repository_url: str) -> bool:
    """Deploy web data to git repository using GitHub App authentication."""
    import shutil
    import tempfile

    from .utils.github_auth import GitHubAppAuth

    try:
        print("🔐 Using GitHub App authentication for deployment...")

        # Create temporary directory for git operations
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"

            # Clone the repository
            print(f"📥 Cloning repository {repository_url}...")
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
                ["git", "config", "user.name", "Ground Events Bot"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )

            # Copy template files from public_template to cloned repo
            public_template_dir = Path.cwd() / "public_template"
            target_public_dir = repo_dir / "public"

            print(f"📋 Copying template files from {public_template_dir}...")
            shutil.copytree(public_template_dir, target_public_dir, dirs_exist_ok=True)

            # Write generated web data to cloned repository
            json_path = target_public_dir / "data.json"
            with open(json_path, "w") as f:
                json.dump(web_data, f, indent=2)

            print(f"📝 Updated data.json with {web_data.get('total_events', 0)} events")

            # Add all files in public directory
            subprocess.run(
                ["git", "add", "public/"], cwd=repo_dir, check=True, capture_output=True
            )

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"],
                cwd=repo_dir,
                capture_output=True,
            )
            if result.returncode == 0:
                print("ℹ️  No changes to deploy")
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
            print(f"🚀 Pushing to {repository_url}...")
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            print("✅ Deployed successfully! Changes will be live shortly.")

            return True

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"❌ Git operation failed: {error_msg}")
        return False
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
        return False


def preview_locally(events: List[FoodTruckEvent]) -> bool:
    """Generate web files locally in public/ directory for preview."""
    import shutil

    try:
        # Generate web data
        web_data = generate_web_data(events)

        # Set up paths
        public_template_dir = Path.cwd() / "public_template"
        local_public_dir = Path.cwd() / "public"

        # Ensure public_template exists
        if not public_template_dir.exists():
            print(f"❌ Template directory not found: {public_template_dir}")
            return False

        # Create or clear public directory
        if local_public_dir.exists():
            shutil.rmtree(local_public_dir)

        # Copy template files to public/
        print(f"📋 Copying template files from {public_template_dir}...")
        shutil.copytree(public_template_dir, local_public_dir)

        # Write generated web data to local public directory
        json_path = local_public_dir / "data.json"
        with open(json_path, "w") as f:
            json.dump(web_data, f, indent=2)

        print(f"✅ Generated local preview: {len(events)} events")
        print(f"📁 Preview files in: {local_public_dir}")
        print("🌐 To serve locally: cd public && python -m http.server 8000")
        print("🔗 Then visit: http://localhost:8000")

        return True

    except Exception as e:
        print(f"❌ Error during local preview generation: {e}")
        return False


def deploy_to_web_with_site_config(
    events: List[FoodTruckEvent], site_config: SiteConfig, git_repo_url: str
) -> bool:
    """Deploy events to web using site-specific configuration."""
    try:
        # Generate web data with site-specific information
        web_data = generate_web_data(events)
        web_data["site_title"] = site_config.website_title
        web_data["site_description"] = site_config.description

        print(f"✅ Generated web data: {len(events)} events")
        print(f"🏷️  Site: {site_config.name} ({site_config.template_type})")
        print(f"📍 Target repository: {git_repo_url}")

        # Use site-specific template and deployment
        return _deploy_with_site_template(web_data, git_repo_url, site_config)

    except Exception as e:
        print(f"❌ Error during site deployment: {e}")
        return False


def preview_locally_with_site_config(
    events: List[FoodTruckEvent], site_config: SiteConfig
) -> bool:
    """Generate local preview using site-specific template."""
    import shutil

    try:
        # Generate web data with site-specific information
        web_data = generate_web_data(events)
        web_data["site_title"] = site_config.website_title
        web_data["site_description"] = site_config.description

        # Set up paths
        template_dir = Path.cwd() / "templates" / site_config.template_type
        local_public_dir = Path.cwd() / "generated_sites" / site_config.name.lower().replace(" ", "-")

        # Ensure template exists
        if not template_dir.exists():
            print(f"❌ Template directory not found: {template_dir}")
            return False

        # Create or clear local preview directory
        if local_public_dir.exists():
            shutil.rmtree(local_public_dir)

        # Copy template files to preview directory
        print(f"📋 Copying template files from {template_dir}...")
        shutil.copytree(template_dir, local_public_dir)

        # Write generated web data to local preview directory
        json_path = local_public_dir / "data.json"
        with open(json_path, "w") as f:
            json.dump(web_data, f, indent=2)

        print(f"✅ Generated local preview: {len(events)} events")
        print(f"🏷️  Site: {site_config.name} ({site_config.template_type})")
        print(f"📁 Preview files in: {local_public_dir}")
        print("🌐 To serve locally: cd generated_sites/[site-name] && python -m http.server 8000")
        print("🔗 Then visit: http://localhost:8000")

        return True

    except Exception as e:
        print(f"❌ Error during local preview generation: {e}")
        return False


def _deploy_with_site_template(web_data: dict, repository_url: str, site_config: SiteConfig) -> bool:
    """Deploy web data using site-specific template."""
    import shutil
    import tempfile

    from .utils.github_auth import GitHubAppAuth

    try:
        print("🔐 Using GitHub App authentication for deployment...")

        # Create temporary directory for git operations
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"

            # Clone the repository
            print(f"📥 Cloning repository {repository_url}...")
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
                ["git", "config", "user.name", "Ground Events Bot"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )

            # Copy template files from templates/[template_type] to cloned repo
            template_dir = Path.cwd() / "templates" / site_config.template_type
            target_public_dir = repo_dir / "public"

            if not template_dir.exists():
                raise FileNotFoundError(f"Template directory not found: {template_dir}")

            print(f"📋 Copying template files from {template_dir}...")
            shutil.copytree(template_dir, target_public_dir, dirs_exist_ok=True)

            # Write generated web data to cloned repository
            json_path = target_public_dir / "data.json"
            with open(json_path, "w") as f:
                json.dump(web_data, f, indent=2)

            print(f"📝 Updated data.json with {web_data.get('total_events', 0)} events")

            # Add all files in public directory
            subprocess.run(
                ["git", "add", "public/"], cwd=repo_dir, check=True, capture_output=True
            )

            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "diff", "--staged", "--quiet"],
                cwd=repo_dir,
                capture_output=True,
            )
            if result.returncode == 0:
                print("ℹ️  No changes to deploy")
                return True

            # Commit changes
            commit_msg = f"🌐 Update {site_config.name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
            print(f"🚀 Pushing to {repository_url}...")
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=repo_dir,
                check=True,
                capture_output=True,
            )
            print("✅ Deployed successfully! Changes will be live shortly.")

            return True

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"❌ Git operation failed: {error_msg}")
        return False
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
        return False


async def scrape_food_trucks(config_path: Optional[str] = None) -> tuple:
    """Scrape food truck schedules from all configured breweries."""
    breweries = load_brewery_config(config_path)

    if not breweries:
        print("No breweries configured.")
        return [], []

    coordinator = ScraperCoordinator()
    events = await coordinator.scrape_all(breweries)
    errors = coordinator.get_errors()

    return events, errors


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Multi-site event aggregation system"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Multi-site options
    parser.add_argument(
        "--site",
        help="Site configuration name (e.g., ballard-food-trucks, seattle-concerts)"
    )
    parser.add_argument(
        "--all-sites",
        action="store_true",
        help="Process all available site configurations"
    )
    parser.add_argument(
        "--list-sites",
        action="store_true",
        help="List all available site configurations"
    )

    # Legacy options (backwards compatibility)
    parser.add_argument(
        "--config", "-c", help="Path to brewery configuration JSON file (legacy)"
    )

    # Common options
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--deploy",
        "-d",
        action="store_true",
        help="Deploy results to web (generate JSON and push to git)",
    )
    parser.add_argument(
        "--git-repo",
        help="Git repository URL for deployment (overrides site config)",
    )
    parser.add_argument(
        "--preview",
        "-p",
        action="store_true",
        help="Generate web files locally for preview",
    )

    args = parser.parse_args(argv)

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("🌐 Ground Events - Multi-Site Event Aggregation")
    print("=" * 55)

    try:
        # Handle list-sites command
        if args.list_sites:
            site_loader = SiteConfigLoader()
            sites = site_loader.list_available_sites()
            if sites:
                print("Available site configurations:")
                for site in sites:
                    print(f"  • {site}")
            else:
                print("No site configurations found")
            return 0

        # Handle all-sites command
        if args.all_sites:
            site_loader = SiteConfigLoader()
            site_configs = site_loader.load_all_sites()

            if not site_configs:
                print("No site configurations found")
                return 1

            total_success = 0
            total_errors = 0

            for site_config in site_configs:
                print(f"\n🔄 Processing site: {site_config.name}")
                print("-" * 40)

                # Process this site
                result = process_single_site(site_config, args)
                if result == 0:
                    total_success += 1
                else:
                    total_errors += 1

            print(f"\n📊 Summary: {total_success} sites succeeded, {total_errors} sites failed")
            return 0 if total_errors == 0 else 2

        # Handle single site or legacy mode
        if args.config:
            # Legacy mode: use JSON config
            events, errors = asyncio.run(scrape_food_trucks(args.config))
        else:
            # New mode: use site configuration
            site_config = load_site_config(args.site)
            return process_single_site(site_config, args)

        # Legacy mode output
        output = format_events_output(events, errors)
        print(output)

        # Deploy to web if requested
        if args.deploy and events:
            deploy_to_web(events, args.git_repo)

        # Generate local preview if requested
        if args.preview and events:
            preview_locally(events)

        # Return appropriate exit code
        if errors and not events:
            return 1  # Complete failure
        elif errors:
            return 2  # Partial success
        else:
            return 0  # Complete success

    except Exception as e:
        print(f"Critical Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def process_single_site(site_config: SiteConfig, args) -> int:
    """Process a single site configuration."""
    try:
        # Convert site config to legacy format for compatibility
        breweries = convert_site_to_breweries(site_config)

        # Scrape events
        events, errors = asyncio.run(scrape_food_trucks_from_breweries(breweries))

        # Convert back to legacy format for output
        food_truck_events = convert_events_to_food_truck_events(events)

        # Show output
        output = format_events_output(food_truck_events, errors)
        print(output)

        # Deploy to web if requested
        if args.deploy and food_truck_events:
            # Use site-specific repository URL unless overridden
            repo_url = args.git_repo or site_config.repository_url
            deploy_to_web_with_site_config(food_truck_events, site_config, repo_url)

        # Generate local preview if requested
        if args.preview and food_truck_events:
            preview_locally_with_site_config(food_truck_events, site_config)

        # Return appropriate exit code
        if errors and not food_truck_events:
            return 1  # Complete failure
        elif errors:
            return 2  # Partial success
        else:
            return 0  # Complete success

    except Exception as e:
        print(f"Error processing site '{site_config.name}': {e}")
        return 1


async def scrape_food_trucks_from_breweries(breweries: List[Brewery]) -> tuple:
    """Scrape events from breweries (updated function name for clarity)."""
    if not breweries:
        print("No sources configured.")
        return [], []

    coordinator = ScraperCoordinator()
    events = await coordinator.scrape_all(breweries)
    errors = coordinator.get_errors()

    return events, errors


if __name__ == "__main__":
    sys.exit(main())
