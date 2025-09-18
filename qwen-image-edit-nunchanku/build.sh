#!/bin/bash
set -e

# Build script for Qwen Image Edit Nunchanku API

IMAGE_NAME="qwen-image-edit-api"
TAG="latest"
REGISTRY=${REGISTRY:-""}

echo "Building Qwen Image Edit Nunchanku API Docker image..."

# Build the image
docker build -t "${IMAGE_NAME}:${TAG}" .

echo "Build complete: ${IMAGE_NAME}:${TAG}"

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