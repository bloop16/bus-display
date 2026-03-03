# Dockerfile for ARM emulation testing
FROM arm32v7/python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pil \
    python3-flask \
    python3-requests \
    python3-bs4 \
    python3-lxml \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy application files
COPY . .

# Create config directory
RUN mkdir -p config logs

# Expose web interface port
EXPOSE 5000

# Default: Run in mock mode (no GPIO hardware)
CMD ["python3", "main.py", "--mock-display", "--continuous", "--interval", "5"]
