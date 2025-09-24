"""
Site configuration loader for multi-site event aggregation.

Loads YAML configuration files that define individual websites.
"""

import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..models import SiteConfig, EventSource


class SiteConfigLoader:
    """Loads and validates site configurations from YAML files."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            self.config_dir = Path(__file__).parent / "sites"
        else:
            self.config_dir = Path(config_dir)

    def load_site_config(self, site_name: str) -> SiteConfig:
        """Load a specific site configuration by name."""
        config_path = self.config_dir / f"{site_name}.yaml"

        if not config_path.exists():
            raise FileNotFoundError(f"Site configuration not found: {config_path}")

        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)

        return self._parse_site_config(config_data, site_name)

    def list_available_sites(self) -> List[str]:
        """List all available site configurations."""
        if not self.config_dir.exists():
            return []

        sites = []
        for yaml_file in self.config_dir.glob("*.yaml"):
            sites.append(yaml_file.stem)

        return sorted(sites)

    def load_all_sites(self) -> List[SiteConfig]:
        """Load all available site configurations."""
        sites = []
        for site_name in self.list_available_sites():
            try:
                site_config = self.load_site_config(site_name)
                sites.append(site_config)
            except Exception as e:
                # Log error but continue with other sites
                print(f"Warning: Failed to load site '{site_name}': {e}")

        return sites

    def _parse_site_config(self, config_data: Dict[str, Any], site_name: str) -> SiteConfig:
        """Parse raw YAML data into SiteConfig object."""
        site_data = config_data.get("site", {})

        # Validate required fields
        required_fields = ["name", "template_type", "website_title", "repository_url", "description"]
        for field in required_fields:
            if field not in site_data:
                raise ValueError(f"Missing required field '{field}' in site configuration")

        # Parse sources
        sources_data = config_data.get("sources", [])
        sources = []

        for source_data in sources_data:
            # Validate required source fields
            source_required = ["key", "name", "url", "parser_type"]
            for field in source_required:
                if field not in source_data:
                    raise ValueError(f"Missing required field '{field}' in source configuration")

            source = EventSource(
                key=source_data["key"],
                name=source_data["name"],
                url=source_data["url"],
                parser_type=source_data["parser_type"],
                parser_config=source_data.get("parser_config", {})
            )
            sources.append(source)

        return SiteConfig(
            name=site_data["name"],
            template_type=site_data["template_type"],
            website_title=site_data["website_title"],
            repository_url=site_data["repository_url"],
            description=site_data["description"],
            sources=sources,
            event_category=site_data.get("event_category")
        )