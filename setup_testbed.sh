# Clone DeathStarBench repository
echo "Cloning DeathStarBench repository..."
git clone https://github.com/delimitrou/DeathStarBench.git

# Navigate to Social Network directory
cd DeathStarBench/socialNetwork

# Start the social network application
echo "Starting DeathStarBench Social Network application..."
docker compose up -d

# Verify services are running
echo "Checking service status..."
docker compose ps
docker ps --format "table {{.Names}}\t{{.Ports}}"

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