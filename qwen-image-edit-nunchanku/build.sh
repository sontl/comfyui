#!/bin/bash
set -e

# Build script for Qwen Image Edit Nunchanku API

IMAGE_NAME="qwen-image-edit-api"
TAG="latest"
REGISTRY=${REGISTRY:-""}

echo "Building Qwen Image Edit Nunchanku API Docker image..."
echo "Working directory: $(pwd)"
echo "Docker version: $(docker --version)"

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    echo "Error: Docker daemon is not running or accessible"
    echo "Please start Docker and ensure you have proper permissions"
    exit 1
fi

# Build the image with better error handling
echo "Starting Docker build..."
if docker build -t "${IMAGE_NAME}:${TAG}" .; then
    echo "Build complete: ${IMAGE_NAME}:${TAG}"
else
    echo "Build failed! Please check the error messages above."
    exit 1
fi

# Tag for registry if specified
if [[ -n "${REGISTRY}" ]]; then
    FULL_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
    docker tag "${IMAGE_NAME}:${TAG}" "${FULL_TAG}"
    echo "Tagged for registry: ${FULL_TAG}"
    
    # Ask if user wants to push
    read -p "Push to registry? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker push "${FULL_TAG}"
        echo "Pushed to registry: ${FULL_TAG}"
    fi
fi

echo "Image ready for deployment!"
echo ""
echo "To run locally:"
echo "docker run --gpus all -p 8000:8000 ${IMAGE_NAME}:${TAG}"
echo ""
echo "To run with model caching:"
echo "docker run --gpus all -p 8000:8000 -v \$(pwd)/models:/app/models ${IMAGE_NAME}:${TAG}"