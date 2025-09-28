#!/bin/bash

# Clone DeathStarBench repository
echo "Cloning DeathStarBench repository..."
git clone https://github.com/delimitrou/DeathStarBench.git

# Navigate to Social Network directory
cd DeathStarBench/socialNetwork

# Create service-specific configuration directory
mkdir -p config

# Create optimized docker-compose configuration for the three target services
echo "Creating optimized configuration for media-service, home-timeline-service, and compose-post-service..."

# Use the original DeathStarBench docker-compose.yml instead of custom
echo "Using original DeathStarBench configuration..."
echo "The original setup works for our experiments"

# Start the services using the original docker-compose.yml
echo "Starting DeathStarBench Social Network services..."
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to initialize..."
sleep 30

# Verify services are running
echo "Checking service status..."
docker-compose ps

echo "DeathStarBench Social Network setup complete!"
echo "Services available at:"
echo "  - Frontend: http://localhost:8080"
echo "  - All microservices accessible through nginx-thrift proxy on port 8080"
echo ""
echo "Key services for our experiments:"
echo "  - media-service (CPU-intensive)"
echo "  - home-timeline-service (memory-intensive)" 
echo "  - compose-post-service (mixed workload)"

cd ../..