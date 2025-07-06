"""Shared data models for Temporal workflows."""

from dataclasses import dataclass
from typing import Optional, List

from ..config.settings import DEFAULT_GIT_REPOSITORY


@dataclass
class WorkflowParams:
    """Parameters for the food truck workflow."""
    config_path: Optional[str] = None
    deploy: bool = False
    git_repository_url: str = DEFAULT_GIT_REPOSITORY


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
    deployed: bool = False