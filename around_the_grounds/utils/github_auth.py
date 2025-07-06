"""GitHub App authentication utilities for git operations."""

import base64
import json
import os
import time
from typing import Optional
import jwt
import requests
import logging

logger = logging.getLogger(__name__)

class GitHubAppAuth:
    """Handle GitHub App authentication for git operations."""
    
    def __init__(self):
        self.app_id = os.getenv("GITHUB_APP_ID", "1531147")
        self.client_id = os.getenv("GITHUB_CLIENT_ID", "Iv23lihIZ0x4zfmWyUPe")
        self.private_key_b64 = os.getenv("GITHUB_APP_PRIVATE_KEY_B64")
        self.repo_owner = "steveandroulakis"
        self.repo_name = "around-the-grounds"
        
        if not self.private_key_b64:
            raise ValueError("GITHUB_APP_PRIVATE_KEY_B64 environment variable is required")
    
    def _get_private_key(self) -> str:
        """Decode the base64-encoded private key."""
        try:
            return base64.b64decode(self.private_key_b64).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decode private key: {e}")
    
    def _create_jwt(self) -> str:
        """Create a JWT token for GitHub App authentication."""
        now = int(time.time())
        payload = {
            'iat': now - 60,  # Issued at time (60 seconds ago to account for clock skew)
            'exp': now + 600,  # Expiration time (10 minutes from now)
            'iss': self.app_id  # Issuer (GitHub App ID)
        }
        
        private_key = self._get_private_key()
        return jwt.encode(payload, private_key, algorithm='RS256')
    
    def _get_installation_id(self, jwt_token: str) -> str:
        """Get the installation ID for the repository."""
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/installation"
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            installation_data = response.json()
            return str(installation_data['id'])
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get installation ID: {e}")
            raise ValueError(f"Failed to get GitHub installation ID: {e}")
    
    def _get_installation_token(self, jwt_token: str, installation_id: str) -> str:
        """Get an installation access token using the JWT."""
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
        
        try:
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            return token_data['token']
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get installation token: {e}")
            raise ValueError(f"Failed to get GitHub installation token: {e}")
    
    def get_access_token(self) -> str:
        """Get a GitHub App installation access token."""
        try:
            # Step 1: Create JWT
            jwt_token = self._create_jwt()
            
            # Step 2: Get installation ID
            installation_id = self._get_installation_id(jwt_token)
            
            # Step 3: Get installation token
            access_token = self._get_installation_token(jwt_token, installation_id)
            
            logger.info("Successfully obtained GitHub App access token")
            return access_token
            
        except Exception as e:
            logger.error(f"GitHub App authentication failed: {e}")
            raise
    
    def configure_git_auth(self, access_token: str) -> None:
        """Configure git to use the GitHub App token for authentication."""
        import subprocess
        
        # Configure git to use the token for this repository
        repo_url = f"https://x-access-token:{access_token}@github.com/{self.repo_owner}/{self.repo_name}.git"
        
        try:
            # Set the remote URL with the token
            subprocess.run([
                'git', 'remote', 'set-url', 'origin', repo_url
            ], check=True, capture_output=True)
            
            logger.info("Git authentication configured successfully")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure git authentication: {e}")
            raise ValueError(f"Failed to configure git authentication: {e}")


def setup_github_auth() -> None:
    """Set up GitHub App authentication for git operations."""
    try:
        auth = GitHubAppAuth()
        token = auth.get_access_token()
        auth.configure_git_auth(token)
        
        logger.info("GitHub App authentication setup completed")
        
    except Exception as e:
        logger.error(f"GitHub App authentication setup failed: {e}")
        raise