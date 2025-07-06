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
from around_the_grounds.utils.github_auth import setup_github_auth


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
        import tempfile
        import shutil
        from around_the_grounds.utils.github_auth import GitHubAppAuth
        
        try:
            activity.logger.info(f"Starting deployment with {web_data.get('total_events', 0)} events")
            
            # Create temporary directory for git operations
            with tempfile.TemporaryDirectory() as temp_dir:
                repo_dir = Path(temp_dir) / "repo"
                
                # Clone the repository
                repo_url = "https://github.com/steveandroulakis/around-the-grounds.git"
                activity.logger.info(f"Cloning repository to {repo_dir}")
                subprocess.run(['git', 'clone', repo_url, str(repo_dir)], check=True, capture_output=True)
                
                # Configure git user in the cloned repository
                subprocess.run(['git', 'config', 'user.email', 'steve.androulakis@gmail.com'], 
                             cwd=repo_dir, check=True, capture_output=True)
                subprocess.run(['git', 'config', 'user.name', 'Steve Androulakis'], 
                             cwd=repo_dir, check=True, capture_output=True)
                
                # Ensure public directory exists in cloned repo
                public_dir = repo_dir / "public"
                public_dir.mkdir(exist_ok=True)
                
                # Write JSON file to cloned repo
                json_path = public_dir / "data.json"
                with open(json_path, 'w') as f:
                    json.dump(web_data, f, indent=2)
                
                activity.logger.info(f"Generated web data file: {json_path}")
                
                # Check if there are changes to commit
                result = subprocess.run(['git', 'diff', '--quiet', 'HEAD', str(json_path)], 
                                      cwd=repo_dir, capture_output=True)
                if result.returncode == 0:
                    activity.logger.info("No changes to deploy")
                    return True
                
                # Add and commit the data file
                subprocess.run(['git', 'add', str(json_path)], cwd=repo_dir, check=True, capture_output=True)
                
                # Commit changes
                commit_msg = f"🚚 Update food truck data - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_dir, check=True, capture_output=True)
                
                # Set up GitHub App authentication and configure remote
                auth = GitHubAppAuth()
                access_token = auth.get_access_token()
                
                authenticated_url = f"https://x-access-token:{access_token}@github.com/steveandroulakis/around-the-grounds.git"
                subprocess.run(['git', 'remote', 'set-url', 'origin', authenticated_url], 
                             cwd=repo_dir, check=True, capture_output=True)
                
                # Push to origin
                subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo_dir, check=True, capture_output=True)
                activity.logger.info("Deployed to git! Changes will be live shortly.")
                
                return True
                
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            activity.logger.error(f"Git operation failed: {error_msg}")
            raise ValueError(f"Failed to deploy to git: {error_msg}")
        except Exception as e:
            activity.logger.error(f"Error during deployment: {e}")
            raise ValueError(f"Failed to deploy to git: {e}")