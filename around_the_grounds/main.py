"""Main entry point for around-the-grounds CLI."""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from .models import Brewery, FoodTruckEvent
from .scrapers import ScraperCoordinator


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
        "updated": datetime.now().isoformat(),
        "total_events": len(web_events)
    }


def deploy_to_web(events: List[FoodTruckEvent]) -> bool:
    """Generate web data and deploy to Vercel via git."""
    try:
        # Ensure public directory exists
        public_dir = Path("public")
        public_dir.mkdir(exist_ok=True)
        
        # Generate web data
        web_data = generate_web_data(events)
        
        # Write JSON file
        json_path = public_dir / "data.json"
        with open(json_path, 'w') as f:
            json.dump(web_data, f, indent=2)
        
        print(f"✅ Generated web data: {len(events)} events")
        
        # Check if we're in a git repository
        result = subprocess.run(['git', 'status'], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Not in a git repository - skipping deployment")
            return False
        
        # Add and commit the data file
        subprocess.run(['git', 'add', str(json_path)], check=True)
        
        # Check if there are changes to commit
        result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
        if result.returncode == 0:
            print("ℹ️  No changes to deploy")
            return True
        
        # Commit changes
        commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
        
        # Push to origin
        subprocess.run(['git', 'push'], check=True)
        
        print("🚀 Deployed to Vercel! Changes will be live shortly.")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Deployment failed: {e}")
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
            deploy_to_web(events)
        
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