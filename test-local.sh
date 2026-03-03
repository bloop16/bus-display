#!/bin/bash
# Local testing script - No Pi hardware needed!

echo "==================================="
echo "Bus Display - Local Testing"
echo "==================================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker not installed!"
    echo "Install: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "Docker found ✓"

# Enable ARM emulation (one-time setup)
echo ""
echo ">>> Enabling ARM emulation..."
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

if [ $? -eq 0 ]; then
    echo "ARM emulation enabled ✓"
else
    echo "WARNING: ARM emulation setup failed (may already be enabled)"
fi

# Build image
echo ""
echo ">>> Building Docker image..."
docker build -t bus-display:local .

if [ $? -ne 0 ]; then
    echo "ERROR: Build failed!"
    exit 1
fi

echo "Build complete ✓"

# Run container
echo ""
echo ">>> Starting container..."
docker run -d --name bus-display-test -p 5000:5000 bus-display:local

if [ $? -ne 0 ]; then
    echo "ERROR: Container start failed!"
    docker rm -f bus-display-test 2>/dev/null
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
