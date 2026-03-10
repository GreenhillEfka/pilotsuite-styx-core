#!/bin/bash
set -e

TAG=${1:-latest}
IMAGE_NAME="greenhillefka/pilotsuite-core"

echo "Building PilotSuite Core Add-on..."
docker build -t ${IMAGE_NAME}:${TAG} -f Dockerfile ..

echo "Pushing to Docker Hub..."
docker push ${IMAGE_NAME}:${TAG}

echo "Done!"
