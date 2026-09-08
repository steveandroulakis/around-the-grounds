"""Site configuration loader for multi-site event aggregator."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from ..models import SiteConfig, Venue


def _parse_venue(venue_data: Dict[str, Any]) -> Venue:
    """Parse a venue dict into a Venue object."""
    return Venue(
        key=venue_data["key"],
        name=venue_data["name"],
        url=venue_data["url"],
        source_type=venue_data.get("source_type", "html"),
        parser_config=venue_data.get("parser_config", {}),
    )


def site_from_dict(data: Dict[str, Any]) -> SiteConfig:
    """Build a SiteConfig from a plain dict.

    Used both for ``config/sites/<key>.json`` files and for the dict that
    crosses the Temporal activity boundary (see ``site_to_dict``). Every
    optional field falls back to the dataclass default so older payloads that
    predate a field still load.
    """
    venues = [_parse_venue(v) for v in data.get("venues", [])]

    return SiteConfig(
        key=data["key"],
        name=data["name"],
        template=data.get("template", "food-trucks"),
        timezone=data.get("timezone", "America/Los_Angeles"),
        venues=venues,
        target_repo=data.get("target_repo", ""),
        generate_description=data.get("generate_description", True),
        deploy_subdir=data.get("deploy_subdir", ""),
        public_url=data.get("public_url", ""),
        calendar_max_timed_hours=data.get("calendar_max_timed_hours"),
    )


def site_to_dict(site: SiteConfig) -> Dict[str, Any]:
    """Serialize a SiteConfig to a JSON-safe dict (inverse of site_from_dict)."""
    return asdict(site)


def load_site_from_path(path: Path) -> SiteConfig:
    """Load a site config from a direct file path."""
    if not path.exists():
        raise FileNotFoundError(f"Site config not found: {path}")

    with open(path, "r") as f:
        data = json.load(f)

    return site_from_dict(data)


def load_site_config(site_key: str) -> SiteConfig:
    """Load a site config by key from config/sites/."""
    sites_dir = Path(__file__).parent / "sites"
    config_path = sites_dir / f"{site_key}.json"
    return load_site_from_path(config_path)


def load_all_sites() -> List[SiteConfig]:
    """Load all site configs from config/sites/."""
    sites_dir = Path(__file__).parent / "sites"
    if not sites_dir.exists():
        return []

    sites = []
    for config_file in sorted(sites_dir.glob("*.json")):
        sites.append(load_site_from_path(config_file))

    return sites
