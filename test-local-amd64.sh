#!/bin/bash
# Local testing script - AMD64 native (no ARM emulation)

echo "==================================="
echo "Bus Display - Local Testing (AMD64)"
echo "==================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not installed!"
    echo "Install: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "Docker found ✓"

# Build image
echo ""
echo ">>> Building Docker image (AMD64)..."
docker build -f Dockerfile.local -t bus-display:local-amd64 .

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed!"
    exit 1
fi

echo "Build complete ✓"

# Stop any existing container
docker stop bus-display-test 2>/dev/null || true
docker rm bus-display-test 2>/dev/null || true

# Run container
echo ""
echo ">>> Starting container..."
docker run -d --name bus-display-test -p 5000:5000 -e TZ=Europe/Vienna -v "$(pwd)/config:/app/config" bus-display:local-amd64

if [ $? -ne 0 ]; then
    echo "ERROR: Container start failed!"
    exit 1
fi

echo ""
echo "==================================="
echo "✅ Bus Display Running!"
echo "==================================="
echo ""
echo "Web Interface: http://localhost:5000"
echo ""
echo "Logs:"
echo "  docker logs -f bus-display-test"
echo ""
echo "Stop:"
echo "  docker stop bus-display-test"
echo "  docker rm bus-display-test"
echo ""
