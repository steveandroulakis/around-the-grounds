#!/bin/bash
set -e

# Configuration
IMAGE_NAME="steveandroulakis/around-the-grounds-worker"
SYNOLOGY_HOST="admin@192.168.0.20"
SYNOLOGY_SCRIPT="/volume1/docker/scripts/deploy-pull.sh"

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
        print_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check Docker buildx
    if ! docker buildx version &> /dev/null; then
        print_error "Docker buildx not found. Please install Docker buildx."
        exit 1
    fi
    
    # Check if we're logged into Docker Hub
    if ! docker info | grep -q "Username"; then
        print_warning "Not logged into Docker Hub. Attempting login..."
        docker login || {
            print_error "Docker login failed. Please run 'docker login' first."
            exit 1
        }
    fi
    
    # Check SSH access to Synology
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$SYNOLOGY_HOST" "echo 'SSH connection test successful'" &> /dev/null; then
        print_error "Cannot connect to Synology via SSH. Please check SSH key setup."
        exit 1
    fi
    
    print_status "Prerequisites check passed"
}

# Function to build and push Docker image
build_and_push() {
    local tag=${1:-latest}
    local full_image="$IMAGE_NAME:$tag"
    
    print_status "Building and pushing multi-architecture image: $full_image"
    
    # Build and push
    if docker buildx build --platform linux/amd64,linux/arm64 -t "$full_image" --push .; then
        print_status "Build and push successful"
    else
        print_error "Build and push failed"
        exit 1
    fi
    
    # Verify the image was pushed successfully
    print_status "Verifying image: $full_image"
    if docker buildx imagetools inspect "$full_image" &> /dev/null; then
        print_status "Image verification successful"
    else
        print_error "Image verification failed"
        exit 1
    fi
}

# Function to trigger deployment on Synology
trigger_deployment() {
    local tag=${1:-latest}
    
    print_status "Triggering deployment on Synology..."
    
    if ssh "$SYNOLOGY_HOST" "$SYNOLOGY_SCRIPT $tag"; then
        print_status "Deployment triggered successfully"
    else
        print_error "Deployment failed on Synology"
        exit 1
    fi
}

# Main function
main() {
    local tag=${1:-latest}
    local deploy_immediately=${DEPLOY_IMMEDIATELY:-true}
    
    echo "=================================="
    echo "Docker Build and Deploy Script"
    echo "=================================="
    echo "Image: $IMAGE_NAME:$tag"
    echo "Deploy immediately: $deploy_immediately"
    echo "=================================="
    
    # Check prerequisites
    check_prerequisites
    
    # Build and push image
    build_and_push "$tag"
    
    # Deploy if requested
    if [[ "$deploy_immediately" == "true" ]]; then
        trigger_deployment "$tag"
        print_status "Build and deployment completed successfully!"
    else
        print_status "Build completed successfully. Skipping deployment."
        print_status "To deploy manually, run: ssh $SYNOLOGY_HOST '$SYNOLOGY_SCRIPT $tag'"
    fi
}

# Handle command line arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [TAG] [OPTIONS]"
        echo ""
        echo "Arguments:"
        echo "  TAG                  Docker image tag (default: latest)"
        echo ""
        echo "Environment Variables:"
        echo "  DEPLOY_IMMEDIATELY   Set to 'false' to skip deployment (default: true)"
        echo ""
        echo "Examples:"
        echo "  $0                   # Build and deploy with 'latest' tag"
        echo "  $0 v1.2.3            # Build and deploy with 'v1.2.3' tag"
        echo "  DEPLOY_IMMEDIATELY=false $0  # Build only, skip deployment"
        exit 0
        ;;
    --version|-v)
        echo "Deploy Build Script v1.0.0"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac