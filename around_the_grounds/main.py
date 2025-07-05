"""Main entry point for around-the-grounds CLI."""

import argparse
import asyncio
import json
import logging
import sys
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