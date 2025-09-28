# DeathStarBench Social Network Setup

This document describes the setup and configuration of the DeathStarBench Social Network application with focus on three specific microservices for energy efficiency experiments.

## Target Services

The setup focuses on three specific microservices with different workload characteristics:

### 1. Media Service (CPU-Intensive)
- **Port**: 8081
- **Workload Type**: CPU-intensive
- **Description**: Handles image processing and media operations
- **Resource Allocation**: 2 CPU cores, 1GB RAM
- **Use Case**: Image upload, processing, and optimization

### 2. Home Timeline Service (Memory-Intensive)
- **Port**: 8082
- **Workload Type**: Memory-intensive
- **Description**: Handles read-heavy timeline operations
- **Resource Allocation**: 1 CPU core, 2GB RAM
- **Use Case**: Timeline data retrieval and caching

### 3. Compose Post Service (Mixed Workload)
- **Port**: 8083
- **Workload Type**: Mixed (CPU + Memory)
- **Description**: Handles post composition with both CPU and memory operations
- **Resource Allocation**: 1.5 CPU cores, 1.5GB RAM
- **Use Case**: Post creation, validation, and processing

## Setup Instructions

### Prerequisites
- Docker and Docker Compose
- Python 3.5+
- Git

### Quick Setup
```bash
# 1. Configure services
cd testbed
python configure_services.py

# 2. Start the testbed
cd ..
./setup_testbed.sh

# 3. Verify services are running
cd DeathStarBench/socialNetwork
docker-compose -f docker-compose-custom.yml ps
```

### Manual Setup
```bash
# 1. Clone DeathStarBench
git clone https://github.com/delimitrou/DeathStarBench.git
cd DeathStarBench/socialNetwork

# 2. Start with custom configuration
docker-compose -f docker-compose-custom.yml up -d

# 3. Wait for services to initialize
sleep 30

# 4. Verify all services are running
docker-compose -f docker-compose-custom.yml ps
```

## Service Endpoints

Once running, the services will be available at:

- **Frontend**: http://localhost:8080
- **Media Service**: http://localhost:8081
- **Home Timeline Service**: http://localhost:8082
- **Compose Post Service**: http://localhost:8083
- **Redis**: localhost:6379
- **MongoDB**: localhost:27017

## Experiment Configuration

The experiment runner is configured to test different CPU governors against the three workload types:

### CPU Governors Tested
- `performance` - Maximum performance
- `powersave` - Power saving mode
- `userspace` - User-defined frequency
- `ondemand` - Dynamic scaling based on load
- `conservative` - Conservative scaling
- `schedutil` - Scheduler-based scaling

### Load Levels
- **Low**: 50 users, 30 seconds
- **Medium**: 200 users, 30 seconds
- **High**: 600 users, 30 seconds

### Metrics Collected
- Average CPU usage
- Average memory usage
- DRAM energy consumption
- Package energy consumption
- PP0 energy consumption

## Running Experiments

```bash
# From the GreenLab directory
python experiment-runner/experiment-runner orc/RunnerConfig.py
```

## Monitoring and Debugging

### Check Service Logs
```bash
# View logs for a specific service
docker-compose -f docker-compose-custom.yml logs media-service
docker-compose -f docker-compose-custom.yml logs home-timeline-service
docker-compose -f docker-compose-custom.yml logs compose-post-service
```

### Monitor Resource Usage
```bash
# Real-time resource monitoring
docker stats
```

### Service Health Checks
```bash
# Check if services are responding
curl http://localhost:8081/health  # Media service
curl http://localhost:8082/health  # Home timeline service
curl http://localhost:8083/health  # Compose post service
```

## Teardown

```bash
# Stop and remove all services
./teardown_testbed.sh
```

## Configuration Files

- `service-config.json` - Service configuration and resource allocation
- `docker-compose-custom.yml` - Custom Docker Compose configuration
- `configure_services.py` - Service configuration script

## Troubleshooting

### Common Issues

1. **Services not starting**: Check Docker logs and ensure ports are available
2. **Resource constraints**: Adjust resource limits in `docker-compose-custom.yml`
3. **Network issues**: Ensure all services can communicate with Redis and MongoDB
4. **Performance issues**: Monitor resource usage and adjust allocations

### Log Locations
- Docker logs: `docker-compose -f docker-compose-custom.yml logs`
- Experiment logs: `orc/experiments/`
- Service logs: Available through Docker Compose

## Next Steps

1. Verify all services are running correctly
2. Run baseline tests to establish performance metrics
3. Execute experiments with different CPU governors
4. Analyze results for energy efficiency patterns
