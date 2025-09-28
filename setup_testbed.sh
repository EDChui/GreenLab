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

# Create a custom docker-compose file that focuses on our three services
cat > docker-compose-custom.yml << 'EOF'
version: '3.8'

services:
  # Media Service - CPU-intensive workload
  media-service:
    build: ./mediaService
    ports:
      - "8081:8081"
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '1.0'
          memory: 512M
    environment:
      - REDIS_ADDR=redis:6379
      - MONGO_ADDR=mongodb:27017
    depends_on:
      - redis
      - mongodb

  # Home Timeline Service - Memory-intensive workload
  home-timeline-service:
    build: ./homeTimelineService
    ports:
      - "8082:8082"
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 1G
    environment:
      - REDIS_ADDR=redis:6379
      - MONGO_ADDR=mongodb:27017
    depends_on:
      - redis
      - mongodb

  # Compose Post Service - Mixed workload
  compose-post-service:
    build: ./composePostService
    ports:
      - "8083:8083"
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 1.5G
        reservations:
          cpus: '0.75'
          memory: 768M
    environment:
      - REDIS_ADDR=redis:6379
      - MONGO_ADDR=mongodb:27017
    depends_on:
      - redis
      - mongodb

  # Supporting services
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  mongodb:
    image: mongo:4.4
    ports:
      - "27017:27017"
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  # Social Network Frontend
  social-network-ml-microservices:
    build: ./socialNetwork-ml-microservices
    ports:
      - "8080:8080"
    environment:
      - REDIS_ADDR=redis:6379
      - MONGO_ADDR=mongodb:27017
    depends_on:
      - redis
      - mongodb
      - media-service
      - home-timeline-service
      - compose-post-service
EOF

# Start the services with our custom configuration
echo "Starting DeathStarBench Social Network services..."
docker-compose -f docker-compose-custom.yml up -d

# Wait for services to be ready
echo "Waiting for services to initialize..."
sleep 30

# Verify services are running
echo "Checking service status..."
docker-compose -f docker-compose-custom.yml ps

echo "DeathStarBench Social Network setup complete!"
echo "Services available at:"
echo "  - Frontend: http://localhost:8080"
echo "  - Media Service: http://localhost:8081"
echo "  - Home Timeline Service: http://localhost:8082"
echo "  - Compose Post Service: http://localhost:8083"

cd ../..