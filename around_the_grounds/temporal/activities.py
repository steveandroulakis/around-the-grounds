"""Activity implementations for Temporal workflows."""

import asyncio
import json
import logging
import subprocess
from datetime import datetime, time
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from temporalio import activity

# Import functions we need (these are safe to import in activities)
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from around_the_grounds.models import Brewery, FoodTruckEvent
from around_the_grounds.scrapers import ScraperCoordinator  
from around_the_grounds.main import load_brewery_config, generate_web_data, deploy_to_web


class ScrapeActivities:
    """Activities for scraping food truck data."""
    
    @activity.defn
    async def test_connectivity(self) -> str:
        """Test activity connectivity."""
        return "Activity connectivity test successful"
    
    @activity.defn
    async def load_brewery_config(self, config_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Load brewery configuration and return as serializable data."""
        breweries = load_brewery_config(config_path)
        return [
            {
                "key": b.key,
                "name": b.name,
                "url": b.url,
                "parser_config": b.parser_config
            }
            for b in breweries
        ]
    
    @activity.defn
    async def scrape_food_trucks(self, brewery_configs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
        """Scrape food truck data from all breweries."""
        # Convert dicts back to Brewery objects
        breweries = [
            Brewery(
                key=config["key"],
                name=config["name"],
                url=config["url"],
                parser_config=config["parser_config"]
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
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
                "description": event.description,
                "ai_generated_name": event.ai_generated_name,
            }
            for event in events
        ]
        
        serialized_errors = [
            {
                "brewery_name": error.brewery.name,
                "message": error.message
            }
            for error in errors
        ]
        
        return serialized_events, serialized_errors


class DeploymentActivities:
    """Activities for web deployment and git operations."""
    
    @activity.defn
    async def generate_web_data(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate web-friendly JSON data from events."""
        # Reconstruct events and use existing generate_web_data function
        reconstructed_events = []
        for event_data in events:
            event = FoodTruckEvent(
                brewery_key=event_data["brewery_key"],
                brewery_name=event_data["brewery_name"],
                food_truck_name=event_data["food_truck_name"],
                date=datetime.fromisoformat(event_data["date"]),
                start_time=datetime.fromisoformat(event_data["start_time"]) if event_data["start_time"] else None,
                end_time=datetime.fromisoformat(event_data["end_time"]) if event_data["end_time"] else None,
                description=event_data["description"],
                ai_generated_name=event_data["ai_generated_name"],
            )
            reconstructed_events.append(event)
        
        return generate_web_data(reconstructed_events)
    
    @activity.defn
    async def deploy_to_git(self, web_data: Dict[str, Any]) -> bool:
        """Deploy web data to git repository."""
        # Write the web data to public/data.json
        try:
            # Ensure public directory exists
            public_dir = Path("public")
            public_dir.mkdir(exist_ok=True)
            
            # Write JSON file
            json_path = public_dir / "data.json"
            with open(json_path, 'w') as f:
                json.dump(web_data, f, indent=2)
            
            activity.logger.info(f"Generated web data: {web_data.get('total_events', 0)} events")
            
            # Check if we're in a git repository
            result = subprocess.run(['git', 'status'], capture_output=True, text=True)
            if result.returncode != 0:
                activity.logger.warning("Not in a git repository - skipping deployment")
                return False
            
            # Add and commit the data file
            subprocess.run(['git', 'add', str(json_path)], check=True)
            
            # Check if there are changes to commit
            result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
            if result.returncode == 0:
                activity.logger.info("No changes to deploy")
                return True
            
            # Commit changes
            commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
            
            # Push to origin (handle upstream branch issues)
            try:
                subprocess.run(['git', 'push'], check=True)
                activity.logger.info("Deployed to git! Changes will be live shortly.")
            except subprocess.CalledProcessError as e:
                # If push fails, try to set upstream and push again
                if "no upstream branch" in str(e) or "has no upstream branch" in str(e):
                    try:
                        # Get current branch name
                        branch_result = subprocess.run(['git', 'branch', '--show-current'], capture_output=True, text=True, check=True)
                        current_branch = branch_result.stdout.strip()
                        
                        # Set upstream and push
                        subprocess.run(['git', 'push', '--set-upstream', 'origin', current_branch], check=True)
                        activity.logger.info("Set upstream branch and deployed to git! Changes will be live shortly.")
                    except subprocess.CalledProcessError as upstream_error:
                        activity.logger.warning(f"Git push failed, but commit succeeded: {upstream_error}")
                        activity.logger.info("Data committed locally but not pushed to remote")
                        return True  # Still consider success since commit worked
                else:
                    activity.logger.warning(f"Git push failed, but commit succeeded: {e}")
                    activity.logger.info("Data committed locally but not pushed to remote")
                    return True  # Still consider success since commit worked
            
            return True
            
        except subprocess.CalledProcessError as e:
            activity.logger.error(f"Deployment failed: {e}")
            return False
        except Exception as e:
            activity.logger.error(f"Error during deployment: {e}")
            return False