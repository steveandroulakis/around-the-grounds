"""Main entry point for around-the-grounds CLI."""

import argparse
import asyncio
import json
import logging
import os
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

from .config.loader import load_all_sites, load_site_config, load_site_from_path
from .config.settings import get_git_repository_url
from .models import Venue, Event, SiteConfig
from .scrapers.coordinator import ScraperCoordinator, ScrapingError
from .utils.github_auth import _sanitize_url
from .utils.haiku_generator import HaikuGenerator
from .utils.timezone_utils import (
    format_time_with_site_timezone,
    get_timezone_full_name,
    get_timezone_label,
    now_in_site_timezone_naive,
)

logger = logging.getLogger(__name__)


def format_events_output(
    events: List[Event], errors: Optional[List[ScrapingError]] = None
) -> str:
    """Format events and errors for display."""
    output = []

    # Show events
    if events:
        output.append(f"Found {len(events)} events:")
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
            if "Check Instagram" in event.title or "check Instagram" in (
                event.description or ""
            ):
                output.append(
                    f"  ❌ {event.title} @ {event.venue_name}{time_str}"
                )
                if event.description:
                    output.append(f"     {event.description}")
            else:
                if event.extraction_method == "ai-vision":
                    output.append(
                        f"  🎫 {event.title} 🖼️🤖 @ {event.venue_name}{time_str}"
                    )
                else:
                    output.append(
                        f"  🎫 {event.title} @ {event.venue_name}{time_str}"
                    )
                if event.description:
                    output.append(f"     {event.description}")

    # Show errors
    if errors:
        user_messages = [error.to_user_message() for error in errors]
        user_messages = list(dict.fromkeys(user_messages))
        if events:
            output.append("")
            output.append("⚠️  Processing Summary:")
            output.append(f"✅ {len(events)} events found successfully")
            output.append(f"❌ {len(errors)} venues failed")
        else:
            output.append("❌ No events found - all venues failed")

        output.append("")
        output.append("❌ Errors:")
        for message in user_messages:
            output.append(f"  • {message}")

    if not events and not errors:
        output.append("No events found for the next 7 days.")

    return "\n".join(output)


async def _generate_description_for_today(
    events: List[Event], site: SiteConfig
) -> Optional[str]:
    """Generate a haiku for today's events (only if site.generate_description is True)."""
    if not site.generate_description:
        return None

    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.warning(
            "ANTHROPIC_API_KEY not set — skipping haiku generation. "
            "Set the environment variable to enable AI haiku descriptions."
        )
        return None

    try:
        today_local = now_in_site_timezone_naive(site.timezone)
        today = today_local.date()

        today_events = [event for event in events if event.date.date() == today]

        if not today_events:
            logger.debug("No events for today to generate haiku")
            return None

        haiku_generator = HaikuGenerator()
        haiku = await haiku_generator.generate_haiku(
            today_local, today_events, max_retries=2, site_name=site.name
        )

        return haiku

    except Exception as e:
        logger.warning("Haiku generation failed: %s", e, exc_info=True)
        return None


async def _generate_haiku_for_today(events: List[Event]) -> Optional[str]:
    """Backward-compat wrapper: generate haiku without site context."""
    from .models.site import SiteConfig

    dummy_site = SiteConfig(
        key="default",
        name="Food Trucks",
        template="food-trucks",
        timezone="America/Los_Angeles",
        venues=[],
        generate_description=True,
    )
    return await _generate_description_for_today(events, dummy_site)


async def generate_web_data(
    events: List[Event],
    error_messages: Optional[List[str]] = None,
    site: Optional[SiteConfig] = None,
) -> dict:
    """Generate web-friendly JSON data from events."""
    web_events = []
    site_name = site.name if site else "Events"
    site_key = site.key if site else "events"
    site_tz = site.timezone if site else "America/Los_Angeles"
    tz_label = get_timezone_label(site_tz)
    tz_full = get_timezone_full_name(site_tz)
    tz_note = f"All event times are in {tz_full} ({tz_label})."

    for event in events:
        web_event = {
            "date": event.date.isoformat(),
            "title": event.title,
            "venue": event.venue_name,
            "start_time": (
                format_time_with_site_timezone(
                    event.start_time, site_tz, include_timezone=True
                )
                if event.start_time
                else None
            ),
            "end_time": (
                format_time_with_site_timezone(
                    event.end_time, site_tz, include_timezone=True
                )
                if event.end_time
                else None
            ),
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
            # Emit "vision" (not "ai-vision") in the public JSON so downstream
            # templates that key off extraction_method === "vision" keep working.
            # This matches the contract established by the pre-merge Ballard
            # site; venue-specific parsers still use "ai-vision" internally.
            "extraction_method": (
                "vision"
                if event.extraction_method == "ai-vision"
                else event.extraction_method
            ),
            # Legacy keys for backward compat with existing templates
            "vendor": (
                f"{event.title} 🖼️🤖"
                if event.extraction_method == "ai-vision"
                else event.title
            ),
            "location": event.venue_name,
        }
        web_events.append(web_event)

    unique_error_messages = list(dict.fromkeys(error_messages or []))

    # Reuse the prior run's haiku/timestamp when the event set is unchanged.
    # Skips an Anthropic API call on stable days and keeps data.json byte-
    # identical so the deploy's no-op short-circuit can skip the commit.
    # Only the site-aware path caches; the legacy no-site path stays pure
    # so unit tests don't accumulate hidden state.
    cache_path: Optional[Path] = (
        Path.cwd() / ".cache" / "around-the-grounds" / f"{site_key}.json"
        if site is not None
        else None
    )
    description: Optional[str] = None
    updated: Optional[str] = None
    if cache_path is not None and cache_path.exists():
        try:
            prior = json.loads(cache_path.read_text())
            if prior.get("events") == web_events:
                description = prior.get("haiku")
                updated = prior.get("updated")
        except (json.JSONDecodeError, OSError):
            pass

    if updated is None:
        if site:
            description = await _generate_description_for_today(events, site)
        else:
            # Legacy path: try to generate haiku without site context
            try:
                today_local = now_in_site_timezone_naive(site_tz)
                today = today_local.date()
                today_events = [e for e in events if e.date.date() == today]
                if today_events:
                    haiku_generator = HaikuGenerator()
                    description = await haiku_generator.generate_haiku(
                        today_local, today_events, max_retries=2
                    )
            except Exception as e:
                logger.warning("Haiku generation failed: %s", e, exc_info=True)
        updated = datetime.now(timezone.utc).isoformat()

    web_data = {
        "events": web_events,
        "updated": updated,
        "total_events": len(web_events),
        "site_name": site_name,
        "site_key": site_key,
        "timezone": site_tz,
        "timezone_label": tz_label,
        "timezone_note": tz_note,
        "errors": unique_error_messages,
        "haiku": description,
    }

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(web_data))
        except OSError:
            pass

    return web_data


async def deploy_to_web(
    events: List[Event],
    errors: Optional[List[ScrapingError]] = None,
    git_repo_url: Optional[str] = None,
    site: Optional[SiteConfig] = None,
) -> bool:
    """Generate web data and deploy to Vercel via git."""
    try:
        # Determine target repo
        repo_url = git_repo_url
        if not repo_url and site and site.target_repo:
            repo_url = site.target_repo
        repository_url = get_git_repository_url(repo_url)

        error_messages = [error.to_user_message() for error in errors or []]
        error_messages = list(dict.fromkeys(error_messages))
        web_data = await generate_web_data(events, error_messages, site)

        print(f"✅ Generated web data: {len(events)} events")
        print(f"📍 Target repository: {repository_url}")

        # Determine template directory
        if site:
            template_dir_name = site.template
        else:
            template_dir_name = "food-trucks"

        deploy_subdir = site.deploy_subdir if site else ""

        return _deploy_with_github_auth(
            web_data, repository_url, template_dir_name, deploy_subdir
        )

    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
        return False


def _resolve_template_dir(template_dir_name: str) -> Path:
    """Return the template directory path for *template_dir_name*.

    Raises ValueError if the name would escape ``public_templates/`` via path
    traversal (e.g. ``../../etc``).  Falls back to the legacy ``public_template``
    directory when the per-template subdirectory does not exist.
    """
    cwd = Path.cwd()
    multi = cwd / "public_templates" / template_dir_name
    # Validate before the exists() check so a crafted name is rejected even
    # when the traversal target does not exist on disk.
    templates_root = (cwd / "public_templates").resolve()
    resolved = multi.resolve()
    if not str(resolved).startswith(str(templates_root) + os.sep) and resolved != templates_root:
        raise ValueError(
            f"Template path escapes public_templates/: {template_dir_name!r}"
        )
    return multi if multi.exists() else cwd / "public_template"


def _deploy_with_github_auth(
    web_data: dict,
    repository_url: str,
    template_dir_name: str = "food-trucks",
    deploy_subdir: str = "",
) -> bool:
    """Deploy web data to git repository using GitHub App authentication.

    Two strategies, selected by ``deploy_subdir``:

    - Empty (default): fresh ``git init`` + force-push to repo root. Used by
      GitHub Pages–served targets that own the whole repo.
    - Non-empty: clone the repo, write files into that subdirectory, scoped
      ``git add <subdir>/``, and a normal (non-force) push. Used when the
      target repo has other files at root that must be preserved (e.g. a
      Vercel project consuming ``public/``).
    """
    import shutil
    import tempfile

    from .utils.github_auth import GitHubAppAuth

    try:
        print("🔐 Using GitHub App authentication for deployment...")

        public_templates_dir = _resolve_template_dir(template_dir_name)

        # Mint GitHub App access token once and build the authenticated URL upfront
        # so it can be used for both clone (subdir mode) and push (both modes).
        auth = GitHubAppAuth(repository_url)
        access_token = auth.get_access_token()
        authenticated_url = (
            f"https://x-access-token:{access_token}@github.com/"
            f"{auth.repo_owner}/{auth.repo_name}.git"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"

            if deploy_subdir:
                # Subdir mode: clone the existing repo so files outside the
                # subdir (e.g. vercel.json, README.md) survive the update.
                print(f"📥 Cloning {repository_url}...")
                subprocess.run(
                    ["git", "clone", authenticated_url, str(repo_dir)],
                    check=True,
                    capture_output=True,
                )
            else:
                # Root mode: fresh init. Avoids clone failures on empty/new
                # target repos; history gets rewritten by the force-push below.
                repo_dir.mkdir()
                subprocess.run(
                    ["git", "init"], cwd=repo_dir, check=True, capture_output=True
                )
                subprocess.run(
                    ["git", "remote", "add", "origin", authenticated_url],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True,
                )

            subprocess.run(
                ["git", "config", "user.email", "bot@around-the-grounds.app"],
                cwd=repo_dir, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Around the Grounds Bot"],
                cwd=repo_dir, check=True, capture_output=True,
            )

            target_public_dir = repo_dir / deploy_subdir if deploy_subdir else repo_dir
            target_public_dir.mkdir(parents=True, exist_ok=True)

            print(f"📋 Copying template files from {public_templates_dir}...")
            shutil.copytree(public_templates_dir, target_public_dir, dirs_exist_ok=True)

            json_path = target_public_dir / "data.json"
            with open(json_path, "w") as f:
                json.dump(web_data, f, indent=2)

            print(f"📝 Updated data.json with {web_data.get('total_events', 0)} events")

            if deploy_subdir:
                # Scoped add: only touch the subdir we own.
                subprocess.run(
                    ["git", "add", f"{deploy_subdir}/"],
                    cwd=repo_dir, check=True, capture_output=True,
                )
                # In subdir mode (clone), short-circuit no-op updates so the
                # bot doesn't create empty commits when events haven't changed.
                diff_check = subprocess.run(
                    ["git", "diff", "--staged", "--quiet"],
                    cwd=repo_dir, capture_output=True,
                )
                if diff_check.returncode == 0:
                    print("ℹ️  No changes to deploy")
                    return True
            else:
                subprocess.run(
                    ["git", "add", "."],
                    cwd=repo_dir, check=True, capture_output=True,
                )

            site_name = web_data.get("site_name", "Events")
            commit_msg = f"📅 Update {site_name} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=repo_dir, check=True, capture_output=True,
            )

            print(f"🚀 Pushing to {repository_url}...")
            push_cmd = (
                ["git", "push", "origin", "HEAD:main"]
                if deploy_subdir
                else ["git", "push", "--force", "origin", "HEAD:main"]
            )
            subprocess.run(push_cmd, cwd=repo_dir, check=True, capture_output=True)
            print("✅ Deployed successfully! Changes will be live shortly.")

            return True

    except subprocess.CalledProcessError as e:
        raw = e.stderr.decode("utf-8") if e.stderr else str(e)
        print(f"❌ Git operation failed: {_sanitize_url(raw)}")
        return False
    except Exception as e:
        print(f"❌ Error during deployment: {e}")
        return False


async def preview_locally(
    events: List[Event],
    errors: Optional[List[ScrapingError]] = None,
    site: Optional[SiteConfig] = None,
) -> bool:
    """Generate web files locally in public/ directory for preview."""
    import shutil

    try:
        error_messages = [error.to_user_message() for error in errors or []]
        error_messages = list(dict.fromkeys(error_messages))
        web_data = await generate_web_data(events, error_messages, site)

        # Determine template directory
        if site:
            template_dir_name = site.template
        else:
            template_dir_name = "food-trucks"

        public_templates_dir = _resolve_template_dir(template_dir_name)

        local_public_dir = Path.cwd() / "public"

        if not public_templates_dir.exists():
            print(f"❌ Template directory not found: {public_templates_dir}")
            return False

        if local_public_dir.exists():
            shutil.rmtree(local_public_dir)

        print(f"📋 Copying template files from {public_templates_dir}...")
        shutil.copytree(public_templates_dir, local_public_dir)

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


async def scrape_site(site: SiteConfig) -> tuple:
    """Scrape events for a given site config."""
    if not site.venues:
        return [], []

    coordinator = ScraperCoordinator()
    events = await coordinator.scrape_all(site.venues, timezone=site.timezone)
    errors = coordinator.get_errors()

    return events, errors


async def async_main(args: argparse.Namespace) -> int:
    """Async main entry point."""
    site_key: Optional[str] = getattr(args, "site", None)
    config_path: Optional[str] = getattr(args, "config", None)

    # Determine which sites to run
    sites: List[SiteConfig] = []

    if config_path:
        # --config path: load a SiteConfig from the given path
        try:
            sites = [load_site_from_path(Path(config_path))]
        except (FileNotFoundError, KeyError) as e:
            print(f"❌ Config file invalid or not found: {e}")
            return 1
    elif site_key == "all":
        sites = load_all_sites()
        if not sites:
            print("No site configs found in config/sites/")
            return 1
    elif site_key:
        try:
            sites = [load_site_config(site_key)]
        except FileNotFoundError:
            print(f"❌ Site '{site_key}' not found in config/sites/")
            return 1
    else:
        # Default: ballard-food-trucks
        try:
            sites = [load_site_config("ballard-food-trucks")]
        except FileNotFoundError:
            print("❌ Default site 'ballard-food-trucks' not found")
            return 1

    overall_exit = 0
    for site in sites:
        if len(sites) > 1:
            print(f"\n{'='*50}")
            print(f"🌐 {site.name}")
            print("=" * 50)

        events, errors = await scrape_site(site)
        output = format_events_output(events, errors)
        print(output)

        if args.deploy and events:
            await deploy_to_web(
                events, errors, getattr(args, "git_repo", None), site=site
            )

        if args.preview:
            await preview_locally(events, errors, site=site)

        if errors and not events:
            overall_exit = 1
        elif errors:
            overall_exit = max(overall_exit, 2)

    return overall_exit


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Track event schedules across multiple sites"
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "--site",
        "-s",
        help=(
            'Site key to run (e.g. "ballard-food-trucks", "park-slope-music"). '
            'Use "all" to run all configured sites. Default: ballard-food-trucks'
        ),
    )
    parser.add_argument(
        "--config", "-c", help="Path to site or venue configuration JSON file"
    )
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
        help="Git repository URL for deployment override",
    )
    parser.add_argument(
        "--preview",
        "-p",
        action="store_true",
        help="Generate web files locally in public/ directory for preview",
    )

    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("🌐 Around the Grounds - Event Tracker")
    print("=" * 50)

    try:
        return asyncio.run(async_main(args))
    except Exception as e:
        print(f"Critical Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
