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
    # When True, skip the deploy entirely if the new events array matches what is
    # already deployed. The deploy carries the prior data.json's volatile fields
    # (`updated`, `haiku`) forward so the file stays byte-identical and the no-op
    # short-circuit fires. Enabling this also forces a clone in root mode (so the
    # prior data.json is available to diff against). Sites that want a fresh
    # description on every run (e.g. Ballard's hourly weather haiku) must leave
    # this False — otherwise the haiku would be frozen until the event set changes.
    skip_unchanged_deploys: bool = False
