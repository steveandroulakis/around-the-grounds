"""Shared data models for Temporal workflows."""

from dataclasses import dataclass
from typing import List, Optional

from ..config.settings import DEFAULT_GIT_REPOSITORY


@dataclass
class WorkflowParams:
    """Parameters for the food truck workflow."""

    config_path: Optional[str] = None
    deploy: bool = False
    git_repository_url: str = DEFAULT_GIT_REPOSITORY
    max_parallel_scrapes: int = 10
    # Site key for the multi-site path. None resolves to "ballard-food-trucks"
    # inside the workflow so existing persisted schedules continue to work
    # unchanged on first watchtower roll.
    site_key: Optional[str] = None


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""

    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
    deployed: bool = False
