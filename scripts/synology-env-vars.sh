#!/bin/bash
# Secure environment variables for Synology Docker deployment
# This file should be copied to: /volume1/docker/secrets/env-vars.sh
# Set permissions: chmod 600 /volume1/docker/secrets/env-vars.sh
#
# Note: Temporal connection is handled by Docker networking (temporal-net).
# The worker connects to temporal-server:7233 automatically.
# No Temporal credentials are needed for self-hosted setup.

# Claude Vision API
export ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY_HERE"

# GitHub App Configuration
export GITHUB_APP_PRIVATE_KEY_B64="YOUR_GITHUB_APP_PRIVATE_KEY_B64_HERE"

# Optional: Additional configuration
export VISION_ANALYSIS_ENABLED="true"
export VISION_MAX_RETRIES="2"
export VISION_TIMEOUT="30"

# Log configuration
export LOG_LEVEL="INFO"

# Deployment metadata
export DEPLOYMENT_ENVIRONMENT="production"
export DEPLOYMENT_TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"

# Health check configuration
export HEALTH_CHECK_TIMEOUT="60"
export HEALTH_CHECK_RETRIES="3"