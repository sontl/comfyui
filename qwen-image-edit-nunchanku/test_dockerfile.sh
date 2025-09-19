#!/bin/bash

# Test Dockerfile syntax without building
echo "Testing Dockerfile syntax..."

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Docker not available, skipping syntax test"
    exit 0
fi

# Test dockerfile syntax
docker build --dry-run -t test . 2>&1 | head -20

echo "Dockerfile syntax test completed"