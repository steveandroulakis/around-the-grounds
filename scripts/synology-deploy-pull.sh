#!/bin/bash
set -e

# Configuration
CONTAINER_NAME="around-the-grounds-worker"
IMAGE_NAME="steveandroulakis/around-the-grounds-worker"
SECRETS_FILE="/volume1/docker/secrets/env-vars.sh"
CERTS_PATH="/volume1/docker/certs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found on Synology"
        exit 1
    fi
    
    # Check secrets file
    if [[ ! -f "$SECRETS_FILE" ]]; then
        print_error "Secrets file not found: $SECRETS_FILE"
        print_error "Please create the secrets file first"
        exit 1
    fi
    
    # Check certificates directory
    if [[ ! -d "$CERTS_PATH" ]]; then
        print_error "Certificates directory not found: $CERTS_PATH"
        print_error "Please ensure certificates are in place"
        exit 1
    fi
    
    # Source environment variables
    if source "$SECRETS_FILE"; then
        print_status "Environment variables loaded successfully"
    else
        print_error "Failed to load environment variables from $SECRETS_FILE"
        exit 1
    fi
    
    # Check required environment variables
    local required_vars=("TEMPORAL_ADDRESS" "TEMPORAL_NAMESPACE" "ANTHROPIC_API_KEY" "GITHUB_APP_PRIVATE_KEY_B64")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            print_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    print_status "Prerequisites check passed"
}

# Function to get current image for rollback
get_current_image() {
    docker inspect "$CONTAINER_NAME" --format='{{.Config.Image}}' 2>/dev/null || echo ""
}

# Function to stop and remove container
stop_and_remove_container() {
    print_status "Stopping and removing existing container..."
    
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        print_status "Stopping running container: $CONTAINER_NAME"
        docker stop "$CONTAINER_NAME"
    else
        print_status "Container $CONTAINER_NAME is not running"
    fi
    
    if docker ps -a -q -f name="$CONTAINER_NAME" | grep -q .; then
        print_status "Removing container: $CONTAINER_NAME"
        docker rm "$CONTAINER_NAME"
    else
        print_status "Container $CONTAINER_NAME does not exist"
    fi
}

# Function to pull new image
pull_image() {
    local tag=${1:-latest}
    local full_image="$IMAGE_NAME:$tag"
    
    print_status "Pulling new image: $full_image"
    
    if docker pull --platform linux/amd64 "$full_image"; then
        print_status "Image pulled successfully"
    else
        print_error "Failed to pull image: $full_image"
        exit 1
    fi
}

# Function to start new container
start_container() {
    local tag=${1:-latest}
    local full_image="$IMAGE_NAME:$tag"
    
    print_status "Starting new container: $CONTAINER_NAME"
    
    # Start container with all environment variables
    if docker run -d \
        --name "$CONTAINER_NAME" \
        -e TEMPORAL_ADDRESS="$TEMPORAL_ADDRESS" \
        -e TEMPORAL_NAMESPACE="$TEMPORAL_NAMESPACE" \
        -e TEMPORAL_TLS_CERT="/app/certs/steveandroulakis-test-1.sdvdw.crt" \
        -e TEMPORAL_TLS_KEY="/app/certs/steveandroulakis-test-1.sdvdw-pkcs8.key" \
        -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
        -e GITHUB_APP_PRIVATE_KEY_B64="$GITHUB_APP_PRIVATE_KEY_B64" \
        -v "$CERTS_PATH":/app/certs \
        --restart unless-stopped \
        "$full_image"; then
        print_status "Container started successfully"
    else
        print_error "Failed to start container"
        exit 1
    fi
}

# Function to wait for container to be healthy
wait_for_healthy() {
    local timeout=${1:-30}
    local count=0
    
    print_status "Waiting for container to be healthy (timeout: ${timeout}s)..."
    
    while [ $count -lt $timeout ]; do
        if docker ps --filter "name=$CONTAINER_NAME" --filter "status=running" --format "table {{.Names}}" | grep -q "$CONTAINER_NAME"; then
            print_status "Container is running and healthy"
            return 0
        fi
        sleep 1
        ((count++))
    done
    
    print_error "Container health check failed after ${timeout}s"
    
    # Show container logs for debugging
    print_status "Container logs:"
    docker logs "$CONTAINER_NAME" 2>&1 | tail -20
    
    return 1
}

# Function to cleanup old images
cleanup_old_images() {
    print_status "Cleaning up old Docker images..."
    
    # Remove dangling images
    if docker image prune -f; then
        print_status "Cleanup completed"
    else
        print_warning "Cleanup had some issues, but continuing"
    fi
}

# Function to rollback deployment
rollback_deployment() {
    local rollback_image="$1"
    
    if [[ -n "$rollback_image" ]]; then
        print_warning "Rolling back to previous image: $rollback_image"
        
        # Stop current container
        stop_and_remove_container
        
        # Extract tag from image
        local rollback_tag="${rollback_image##*:}"
        
        # Start with previous image
        start_container "$rollback_tag"
        
        if wait_for_healthy 30; then
            print_status "Rollback successful"
        else
            print_error "Rollback failed"
        fi
    else
        print_error "No previous image available for rollback"
    fi
}

# Main deployment function
deploy() {
    local tag=${1:-latest}
    local current_image
    
    print_status "Starting deployment of $IMAGE_NAME:$tag"
    
    # Get current image for potential rollback
    current_image=$(get_current_image)
    if [[ -n "$current_image" ]]; then
        print_status "Current image for rollback: $current_image"
    else
        print_status "No existing container found"
    fi
    
    # Stop and remove existing container
    stop_and_remove_container
    
    # Pull new image
    pull_image "$tag"
    
    # Start new container
    start_container "$tag"
    
    # Wait for container to be healthy
    if wait_for_healthy 60; then
        print_status "Deployment successful!"
        
        # Cleanup old images
        cleanup_old_images
        
        # Show container status
        print_status "Container status:"
        docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
    else
        print_error "Deployment failed - container not healthy"
        
        # Attempt rollback
        rollback_deployment "$current_image"
        
        exit 1
    fi
}

# Main function
main() {
    local tag=${1:-latest}
    
    echo "=================================="
    echo "Synology Docker Deployment Script"
    echo "=================================="
    echo "Container: $CONTAINER_NAME"
    echo "Image: $IMAGE_NAME:$tag"
    echo "=================================="
    
    # Check prerequisites
    check_prerequisites
    
    # Perform deployment
    deploy "$tag"
    
    print_status "Deployment completed successfully!"
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [TAG] [OPTIONS]"
        echo ""
        echo "Arguments:"
        echo "  TAG                  Docker image tag (default: latest)"
        echo ""
        echo "Examples:"
        echo "  $0                   # Deploy with 'latest' tag"
        echo "  $0 v1.2.3            # Deploy with 'v1.2.3' tag"
        echo ""
        echo "Files required:"
        echo "  $SECRETS_FILE     # Environment variables"
        echo "  $CERTS_PATH/                 # TLS certificates"
        exit 0
        ;;
    --version|-v)
        echo "Synology Deploy Script v1.0.0"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac