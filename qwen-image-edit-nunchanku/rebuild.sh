#!/bin/bash
set -e

echo "=== Qwen Image Edit Nunchanku API - Clean Rebuild ==="

IMAGE_NAME="qwen-image-edit-api"
TAG="latest"
REGISTRY=${REGISTRY:-""}

# Clean up any existing images
echo "Cleaning up old images..."
docker rmi "${IMAGE_NAME}:latest" 2>/dev/null || true
docker rmi "${IMAGE_NAME}:${TAG}" 2>/dev/null || true

# Build with no cache to ensure fresh build
echo "Building fresh image (no cache)..."
docker build --no-cache -t "${IMAGE_NAME}:${TAG}" .

# Also tag as latest
docker tag "${IMAGE_NAME}:${TAG}" "${IMAGE_NAME}:latest"

echo "Build complete!"
echo "Image: ${IMAGE_NAME}:${TAG}"

# Tag for registry if specified
if [[ -n "${REGISTRY}" ]]; then
    FULL_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
    docker tag "${IMAGE_NAME}:${TAG}" "${FULL_TAG}"
    echo "Tagged for registry: ${FULL_TAG}"
    
    read -p "Push to registry? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker push "${FULL_TAG}"
        echo "Pushed: ${FULL_TAG}"
    fi
fi

echo ""
echo "=== Test locally with: ==="
echo "docker run --rm --gpus all -p 8000:8000 ${IMAGE_NAME}:${TAG}"
echo ""
echo "=== Deploy with: ==="
if [[ -n "${REGISTRY}" ]]; then
    echo "Image: ${REGISTRY}/${IMAGE_NAME}:${TAG}"
else
    echo "Image: ${IMAGE_NAME}:${TAG}"
fi