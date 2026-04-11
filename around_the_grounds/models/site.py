from dataclasses import dataclass, field
from typing import List

from .brewery import Venue


@dataclass
class SiteConfig:
    key: str
    name: str
    template: str
    timezone: str
    venues: List[Venue]
    target_repo: str = ""
    generate_description: bool = True
    # Subdirectory within the target repo where template + data.json are written.
    # Empty string (default) writes to the repo root — used by sites served from
    # GitHub Pages at the repo root. Non-empty (e.g. "public") writes to that
    # subdirectory — used when the target repo is consumed by a host like Vercel
    # whose build output is scoped to a subfolder. The value also selects the
    # deploy strategy: empty → init + force-push, non-empty → clone + scoped add.
    deploy_subdir: str = ""
