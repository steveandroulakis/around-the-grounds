import os
from dataclasses import dataclass
from typing import Optional


# Git repository configuration
DEFAULT_GIT_REPOSITORY = "https://github.com/steveandroulakis/ballard-food-trucks.git"


def get_git_repository_url(override_url: Optional[str] = None) -> str:
    """Get git repository URL with fallback chain: override -> env -> default."""
    return override_url or os.getenv("GIT_REPOSITORY_URL") or DEFAULT_GIT_REPOSITORY


@dataclass
class VisionConfig:
    """Configuration for vision analysis functionality."""
    enabled: bool = True
    max_retries: int = 2
    timeout_seconds: int = 30
    api_key: Optional[str] = None
    
    @classmethod
    def from_env(cls):
        """Create configuration from environment variables."""
        return cls(
            enabled=os.getenv('VISION_ANALYSIS_ENABLED', 'true').lower() == 'true',
            max_retries=int(os.getenv('VISION_MAX_RETRIES', '2')),
            timeout_seconds=int(os.getenv('VISION_TIMEOUT', '30')),
            api_key=os.getenv('ANTHROPIC_API_KEY')
        )