# Docker Deployment Automation

This document describes the automated Docker deployment system for the Around the Grounds project.

## Overview

The deployment system consists of:
- **Local build script** (`scripts/deploy-build.sh`) - Builds and pushes Docker images
- **Synology deployment script** - Deploys containers on Synology NAS
- **Environment variables** - Secure configuration management
- **SSH orchestration** - Automated deployment coordination

## Setup Instructions

### 1. Local Machine Setup

The local build script is already created and ready to use:

```bash
# Make sure you're in the project root
cd /Users/steveandroulakis/Code/non-temporal/roundthegrounds

# Test the build script
./scripts/deploy-build.sh --help
```

### 2. Synology NAS Setup

#### Step 1: Create Directory Structure
```bash
# SSH into Synology
ssh admin@192.168.0.20

# Create required directories
sudo mkdir -p /volume1/docker/scripts
sudo mkdir -p /volume1/docker/secrets
sudo mkdir -p /volume1/docker/certs

# Set proper ownership
sudo chown -R admin:administrators /volume1/docker
```

#### Step 2: Copy Scripts to Synology
```bash
# From local machine - copy deployment script
scp scripts/synology-deploy-pull.sh admin@192.168.0.20:/volume1/docker/scripts/deploy-pull.sh

# Copy environment variables template
scp scripts/synology-env-vars.sh admin@192.168.0.20:/volume1/docker/secrets/env-vars.sh

# Set proper permissions on Synology
ssh admin@192.168.0.20 "chmod +x /volume1/docker/scripts/deploy-pull.sh && chmod 600 /volume1/docker/secrets/env-vars.sh"
```

#### Step 3: Copy TLS Certificates
```bash
# Copy your existing certificates to Synology
scp /Users/steveandroulakis/Code/certs/steveandroulakis-test-1.sdvdw.crt admin@192.168.0.20:/volume1/docker/certs/
scp /Users/steveandroulakis/Code/certs/steveandroulakis-test-1.sdvdw-pkcs8.key admin@192.168.0.20:/volume1/docker/certs/

# Set proper permissions
ssh admin@192.168.0.20 "chmod 600 /volume1/docker/certs/*"
```

### 3. SSH Key Setup

Ensure SSH key-based authentication is working:

```bash
# Test SSH connection
ssh admin@192.168.0.20 "echo 'SSH test successful'"

# If this fails, you may need to:
# 1. Copy your SSH public key to Synology
# 2. Enable SSH key authentication in Synology DSM
```

## Usage

### Basic Deployment

```bash
# Build and deploy with latest tag
./scripts/deploy-build.sh

# Build and deploy with specific tag
./scripts/deploy-build.sh v1.2.3

# Build only (skip deployment)
DEPLOY_IMMEDIATELY=false ./scripts/deploy-build.sh
```

### Manual Deployment on Synology

```bash
# SSH into Synology and run deployment manually
ssh admin@192.168.0.20 "/volume1/docker/scripts/deploy-pull.sh latest"
```

### Deployment Process

1. **Build Phase** (Local):
   - Checks prerequisites (Docker, buildx, Docker Hub login)
   - Builds multi-architecture image (amd64, arm64)
   - Pushes to Docker Hub
   - Verifies image was pushed successfully

2. **Deploy Phase** (Synology):
   - Loads environment variables and checks prerequisites
   - Stops and removes existing container
   - Pulls new image with platform specification
   - Starts new container with full configuration
   - Performs health checks
   - Cleans up old images

3. **Error Handling**:
   - Automatic rollback on deployment failure
   - Comprehensive logging with colored output
   - Health check validation with timeout

## Monitoring

### Check Container Status

```bash
# On Synology
ssh admin@192.168.0.20 "docker ps --filter name=around-the-grounds-worker"

# Check logs
ssh admin@192.168.0.20 "docker logs around-the-grounds-worker"

# Check recent logs
ssh admin@192.168.0.20 "docker logs around-the-grounds-worker --tail 50"
```

### Health Checks

The deployment script includes automatic health checks:
- Container running status
- 60-second timeout for startup
- Automatic rollback on failure
- Detailed logging for troubleshooting

## Troubleshooting

### Common Issues

1. **SSH Connection Failed**
   ```bash
   # Check SSH connectivity
   ssh -v admin@192.168.0.20
   
   # Ensure SSH keys are properly configured
   ssh-copy-id admin@192.168.0.20
   ```

2. **Docker Build Failed**
   ```bash
   # Check Docker login
   docker login
   
   # Check buildx
   docker buildx version
   
   # Try building locally first
   docker build -t test-image .
   ```

3. **Container Won't Start**
   ```bash
   # Check container logs
   ssh admin@192.168.0.20 "docker logs around-the-grounds-worker"
   
   # Check if certificates are in place
   ssh admin@192.168.0.20 "ls -la /volume1/docker/certs/"
   
   # Verify environment variables
   ssh admin@192.168.0.20 "source /volume1/docker/secrets/env-vars.sh && env | grep TEMPORAL"
   ```

4. **Health Check Failed**
   ```bash
   # Check container process
   ssh admin@192.168.0.20 "docker exec around-the-grounds-worker ps aux"
   
   # Check container networking
   ssh admin@192.168.0.20 "docker exec around-the-grounds-worker netstat -tlnp"
   ```

### Rollback

If deployment fails, the script automatically attempts rollback:

```bash
# Manual rollback to previous version
ssh admin@192.168.0.20 "/volume1/docker/scripts/deploy-pull.sh previous-tag"

# Check what images are available
ssh admin@192.168.0.20 "docker images | grep around-the-grounds-worker"
```

## Security Considerations

1. **Environment Variables**: Stored in `/volume1/docker/secrets/env-vars.sh` with 600 permissions
2. **TLS Certificates**: Stored in `/volume1/docker/certs/` with 600 permissions
3. **SSH Keys**: Use key-based authentication, not passwords
4. **Docker Hub**: Ensure your Docker Hub credentials are secure

## Future Enhancements

- Add webhook-based deployment triggers
- Implement blue-green deployment strategy
- Add monitoring and alerting integration
- Create deployment status dashboard
- Add automatic backup before deployment