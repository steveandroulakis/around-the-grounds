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
from typing import Optional, List

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    # dotenv is optional, fall back to os.environ
    pass

from .models import Brewery, FoodTruckEvent
from .scrapers import ScraperCoordinator
from .config.settings import get_git_repository_url


def load_brewery_config(config_path: Optional[str] = None) -> List[Brewery]:
    """Load brewery configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent / "config" / "breweries.json"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    breweries = []
    for brewery_data in config.get("breweries", []):
        brewery = Brewery(
            key=brewery_data["key"],
            name=brewery_data["name"],
            url=brewery_data["url"],
            parser_config=brewery_data.get("parser_config", {})
        )
        breweries.append(brewery)
    
    return breweries


def format_events_output(events: List[FoodTruckEvent], errors: list = None) -> str:
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
            if "Check Instagram" in event.food_truck_name or "check Instagram" in (event.description or ""):
                output.append(f"  ❌ {event.food_truck_name} @ {event.brewery_name}{time_str}")
                if event.description:
                    output.append(f"     {event.description}")
            else:
                # Add AI vision indicator for AI-generated names
                if event.ai_generated_name:
                    output.append(f"  🚚 {event.food_truck_name} 🖼️🤖 @ {event.brewery_name}{time_str}")
                else:
                    output.append(f"  🚚 {event.food_truck_name} @ {event.brewery_name}{time_str}")
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
    """Generate web-friendly JSON data from events."""
    web_events = []
    
    for event in events:
        # Convert event to web format
        web_event = {
            "date": event.date.isoformat(),
            "vendor": event.food_truck_name,
            "location": event.brewery_name,
            "start_time": event.start_time.strftime("%I:%M %p") if event.start_time else None,
            "end_time": event.end_time.strftime("%I:%M %p") if event.end_time else None,
            "description": event.description,
        }
        
        # Add AI extraction indicator
        if event.ai_generated_name:
            web_event["extraction_method"] = "vision"
            web_event["vendor"] = f"{event.food_truck_name} 🖼️🤖"
        
        web_events.append(web_event)
    
    return {
        "events": web_events,
        "updated": datetime.now(timezone.utc).isoformat(),
        "total_events": len(web_events)
    }


def deploy_to_web(events: List[FoodTruckEvent], git_repo_url: Optional[str] = None) -> bool:
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
    import tempfile
    import shutil
    from .utils.github_auth import GitHubAppAuth
    
    try:
        print(f"🔐 Using GitHub App authentication for deployment...")
        
        # Create temporary directory for git operations
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_dir = Path(temp_dir) / "repo"
            
            # Clone the repository
            print(f"📥 Cloning repository {repository_url}...")
            subprocess.run(['git', 'clone', repository_url, str(repo_dir)], check=True, capture_output=True)
            
            # Configure git user in the cloned repository
            subprocess.run(['git', 'config', 'user.email', 'steve.androulakis@gmail.com'], 
                         cwd=repo_dir, check=True, capture_output=True)
            subprocess.run(['git', 'config', 'user.name', 'Around the Grounds Bot'], 
                         cwd=repo_dir, check=True, capture_output=True)
            
            # Copy template files from public_template to cloned repo
            public_template_dir = Path.cwd() / "public_template"
            target_public_dir = repo_dir / "public"
            
            print(f"📋 Copying template files from {public_template_dir}...")
            shutil.copytree(public_template_dir, target_public_dir, dirs_exist_ok=True)
            
            # Write generated web data to cloned repository
            json_path = target_public_dir / "data.json"
            with open(json_path, 'w') as f:
                json.dump(web_data, f, indent=2)
            
            print(f"📝 Updated data.json with {web_data.get('total_events', 0)} events")
            
            # Add all files in public directory
            subprocess.run(['git', 'add', 'public/'], cwd=repo_dir, check=True, capture_output=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', 'diff', '--staged', '--quiet'], cwd=repo_dir, capture_output=True)
            if result.returncode == 0:
                print("ℹ️  No changes to deploy")
                return True
            
            # Commit changes
            commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_dir, check=True, capture_output=True)
            
            # Set up GitHub App authentication and configure remote
            auth = GitHubAppAuth(repository_url)
            access_token = auth.get_access_token()
            
            authenticated_url = f"https://x-access-token:{access_token}@github.com/{auth.repo_owner}/{auth.repo_name}.git"
            subprocess.run(['git', 'remote', 'set-url', 'origin', authenticated_url], 
                         cwd=repo_dir, check=True, capture_output=True)
            
            # Push to origin
            print(f"🚀 Pushing to {repository_url}...")
            subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo_dir, check=True, capture_output=True)
            print("✅ Deployed successfully! Changes will be live shortly.")
            
            return True
            
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
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


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Track food truck schedules and locations"
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to brewery configuration JSON file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--deploy", "-d",
        action="store_true",
        help="Deploy results to web (generate JSON and push to git)"
    )
    parser.add_argument(
        "--git-repo",
        help="Git repository URL for deployment (default: ballard-food-trucks)"
    )
    
    args = parser.parse_args(argv)
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🍺 Around the Grounds - Food Truck Tracker")
    print("=" * 50)
    
    try:
        events, errors = asyncio.run(scrape_food_trucks(args.config))
        output = format_events_output(events, errors)
        print(output)
        
        # Deploy to web if requested
        if args.deploy and events:
            deploy_to_web(events, args.git_repo)
        
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


if __name__ == "__main__":
    sys.exit(main())