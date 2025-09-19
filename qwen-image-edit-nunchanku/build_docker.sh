#!/bin/bash

###############################################################################
# DOCKER BUILD SCRIPT FOR QWEN IMAGE EDIT NUNCHANKU API
# Builds the optimized Docker image with pre-downloaded models
###############################################################################

set -e  # Exit on any error

# Configuration
IMAGE_NAME="qwen-image-edit-api"
IMAGE_TAG="latest"
BUILD_CONTEXT="."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    error "Docker daemon is not running. Please start Docker and try again."
    exit 1
fi

log "Starting Docker build for ${IMAGE_NAME}:${IMAGE_TAG}"

# Check required files
REQUIRED_FILES=(
    "Dockerfile"
    "main.py"
    "api_requirements.txt"
    "start_qwen_api.sh"
    "verify_models.py"
    "download_base_model.py"
    "download_nunchaku_models.py"
)

log "Checking required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file not found: $file"
        exit 1
    fi
    log "✓ Found: $file"
done

# Check required directories
REQUIRED_DIRS=(
    "models"
    "services"
    "utils"
)

log "Checking required directories..."
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
        error "Required directory not found: $dir"
        exit 1
    fi
    log "✓ Found: $dir/"
done

# Display build information
log "Build Configuration:"
log "  Image Name: ${IMAGE_NAME}:${IMAGE_TAG}"
log "  Build Context: ${BUILD_CONTEXT}"
log "  Docker Version: $(docker --version)"

# Check available disk space
AVAILABLE_SPACE=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
if [ "$AVAILABLE_SPACE" -lt 20 ]; then
    warning "Low disk space available (${AVAILABLE_SPACE}GB). Build may fail if insufficient space."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "Build cancelled by user"
        exit 0
    fi
fi

# Start build
log "Starting Docker build (this may take 10-15 minutes)..."
log "Build will download ~8-11GB of models during the process"

BUILD_START_TIME=$(date +%s)

# Build with progress and error handling
if docker build \
    --tag "${IMAGE_NAME}:${IMAGE_TAG}" \
    --progress=plain \
    "${BUILD_CONTEXT}"; then
    
    BUILD_END_TIME=$(date +%s)
    BUILD_DURATION=$((BUILD_END_TIME - BUILD_START_TIME))
    BUILD_MINUTES=$((BUILD_DURATION / 60))
    BUILD_SECONDS=$((BUILD_DURATION % 60))
    
    success "Docker build completed successfully!"
    log "Build time: ${BUILD_MINUTES}m ${BUILD_SECONDS}s"
    
    # Get image size
    IMAGE_SIZE=$(docker images "${IMAGE_NAME}:${IMAGE_TAG}" --format "table {{.Size}}" | tail -n 1)
    log "Image size: ${IMAGE_SIZE}"
    
    # Verify the image
    log "Verifying built image..."
    if docker run --rm "${IMAGE_NAME}:${IMAGE_TAG}" python3 /app/verify_models.py; then
        success "Image verification passed!"
    else
        warning "Image verification failed, but image was built successfully"
    fi
    
    log "Build Summary:"
    log "  ✓ Image: ${IMAGE_NAME}:${IMAGE_TAG}"
    log "  ✓ Size: ${IMAGE_SIZE}"
    log "  ✓ Build time: ${BUILD_MINUTES}m ${BUILD_SECONDS}s"
    log ""
    log "To run the container:"
    log "  docker run -p 8000:8000 --gpus all ${IMAGE_NAME}:${IMAGE_TAG}"
    log ""
    log "To test the API:"
    log "  curl http://localhost:8000/health"
    
else
    error "Docker build failed!"
    log "Common issues and solutions:"
    log "  1. Network issues: Check internet connection for model downloads"
    log "  2. Disk space: Ensure at least 20GB free space"
    log "  3. Memory: Ensure sufficient RAM for build process"
    log "  4. Docker daemon: Restart Docker if needed"
    exit 1
fi