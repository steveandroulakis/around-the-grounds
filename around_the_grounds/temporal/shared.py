"""Shared data models for Temporal workflows."""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class WorkflowParams:
    """Parameters for the food truck workflow."""
    config_path: Optional[str] = None
    deploy: bool = False


@dataclass
class WorkflowResult:
    """Result of a workflow execution."""
    success: bool
    message: str
    events_count: Optional[int] = None
    errors: Optional[List[str]] = None
    deployed: bool = False