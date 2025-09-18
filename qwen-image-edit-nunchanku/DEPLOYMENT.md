# Qwen Image Edit Nunchanku Deployment Guide

This guide provides comprehensive deployment instructions for the Qwen Image Edit Nunchanku API service across different environments.

## Prerequisites

1. **Docker**: Version 20.10+ (for containerized deployment)
2. **NVIDIA GPU**: RTX 4090 or equivalent with 6GB+ VRAM
3. **CUDA**: Version 12.2 or higher
4. **Python**: 3.11+ (for local deployment)
5. **Storage**: 10GB+ free disk space for model cache

## Deployment Options

### Option 1: Docker Deployment (Recommended)

#### Quick Start

```bash
# Clone and navigate to project
git clone <repository-url>
cd qwen-image-edit-nunchanku

# Build the Docker image
docker build -t qwen-image-edit-api:latest .

# Run with GPU support
docker run --gpus all -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -e MODEL_CACHE_DIR=/app/models \
  --name qwen-api \
  qwen-image-edit-api:latest
```

#### Production Docker Deployment

```bash
# Build with production configuration
docker build \
  --build-arg ENVIRONMENT=production \
  --build-arg LOG_LEVEL=INFO \
  -t qwen-image-edit-api:prod .

# Run with production settings
docker run -d --restart=unless-stopped \
  --gpus all \
  -p 8000:8000 \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/logs:/app/logs \
  -e ENVIRONMENT=production \
  -e LOG_LEVEL=INFO \
  -e API_HOST=0.0.0.0 \
  -e API_PORT=8000 \
  --name qwen-api-prod \
  qwen-image-edit-api:prod
```

### Option 2: Local Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r api_requirements.txt

# Set environment variables
export MODEL_CACHE_DIR=./models
export API_HOST=0.0.0.0
export API_PORT=8000
export LOG_LEVEL=DEBUG
export ENVIRONMENT=development

# Start the service
python main.py
```

### Option 3: Using Startup Script

```bash
# Make the script executable
chmod +x start_qwen_api.sh

# Configure environment (optional)
export API_HOST=0.0.0.0
export API_PORT=8000
export MODEL_CACHE_DIR=./models

# Run the startup script
./start_qwen_api.sh
```

## Cloud Deployment

### Docker Compose Deployment

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  qwen-api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
    environment:
      - API_HOST=0.0.0.0
      - API_PORT=8000
      - MODEL_CACHE_DIR=/app/models
      - LOG_LEVEL=INFO
      - ENVIRONMENT=production
      - CUDA_VISIBLE_DEVICES=0
      - PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
      - TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 2m

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - qwen-api
    restart: unless-stopped
```

Run with:
```bash
docker-compose up -d
```

### Kubernetes Deployment

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: qwen-image-edit-api
  labels:
    app: qwen-api
spec:
  replicas: 1
  selector:
    matchLabels:
      app: qwen-api
  template:
    metadata:
      labels:
        app: qwen-api
    spec:
      containers:
      - name: qwen-api
        image: qwen-image-edit-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: API_HOST
          value: "0.0.0.0"
        - name: API_PORT
          value: "8000"
        - name: MODEL_CACHE_DIR
          value: "/app/models"
        - name: LOG_LEVEL
          value: "INFO"
        - name: ENVIRONMENT
          value: "production"
        - name: CUDA_VISIBLE_DEVICES
          value: "0"
        - name: PYTORCH_CUDA_ALLOC_CONF
          value: "max_split_size_mb:512"
        - name: TORCH_INDUCTOR_FORCE_DISABLE_FP8
          value: "1"
        resources:
          requests:
            nvidia.com/gpu: 1
            memory: "8Gi"
            cpu: "2"
          limits:
            nvidia.com/gpu: 1
            memory: "32Gi"
            cpu: "8"
        volumeMounts:
        - name: model-cache
          mountPath: /app/models
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 120
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
      volumes:
      - name: model-cache
        persistentVolumeClaim:
          claimName: qwen-models-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: qwen-api-service
spec:
  selector:
    app: qwen-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: qwen-models-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: fast-ssd
```

Deploy with:
```bash
kubectl apply -f k8s-deployment.yaml
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API server host |
| `API_PORT` | `8000` | API server port |
| `MODEL_CACHE_DIR` | `./models` | Model cache directory |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ENVIRONMENT` | `production` | Environment mode (development, production) |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device selection |
| `PYTORCH_CUDA_ALLOC_CONF` | `max_split_size_mb:512` | CUDA memory allocation |
| `TORCH_INDUCTOR_FORCE_DISABLE_FP8` | `1` | Disable FP8 for compatibility |

### GPU Memory Optimization

#### For RTX 4090 (24GB VRAM)
```bash
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
export TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
```

#### For RTX 3090/4080 (12-16GB VRAM)
```bash
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:256
export TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
```

#### For RTX 3070/4070 (8-12GB VRAM)
```bash
export CUDA_VISIBLE_DEVICES=0
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
export TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
```

## Monitoring and Health Checks

### Health Check Endpoints

- **Basic Health**: `GET /health`
- **Detailed System Info**: `GET /system-info`
- **API Documentation**: `GET /docs`

### Monitoring with Prometheus

Add to your `docker-compose.yml`:

```yaml
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
```

### Log Management

Logs are written to:
- **Docker**: Container logs accessible via `docker logs qwen-api`
- **Local**: Configurable via `LOG_FILE` environment variable
- **Kubernetes**: Available through `kubectl logs`

## Performance Tuning

### Model Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `num_inference_steps` | 8 | 1-50 | Quality vs speed tradeoff |
| `true_cfg_scale` | 1.0 | 0.1-10.0 | Guidance strength |
| `rank` | 128 | 64, 128 | Model complexity |

### Optimization Tips

1. **Reduce Steps**: Use 4-6 steps for faster inference
2. **Lower Rank**: Use rank=64 for speed over quality
3. **Batch Processing**: Process multiple images together
4. **Memory Management**: Enable CPU offloading for large models

## Security

### API Security

```yaml
# Add authentication middleware
environment:
  - API_KEY=your-secret-api-key
  - ENABLE_AUTH=true
```

### Network Security

```bash
# Bind to localhost only
export API_HOST=127.0.0.1

# Use HTTPS with reverse proxy
# Configure nginx or traefik for SSL termination
```

### Container Security

```dockerfile
# Run as non-root user
RUN useradd -m -u 1000 qwen
USER qwen
```

## Troubleshooting

### Common Issues

#### 1. CUDA Out of Memory
```bash
# Check GPU memory
nvidia-smi

# Reduce model parameters
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:256

# Enable CPU offloading
# Modify service configuration
```

#### 2. Slow Model Loading
```bash
# Use persistent volume for model cache
docker run -v /host/models:/app/models qwen-image-edit-api

# Pre-download models
docker run --rm -v $(pwd)/models:/app/models qwen-image-edit-api python -c "from services.image_edit_service import ImageEditService; ImageEditService().initialize()"
```

#### 3. Service Won't Start
```bash
# Check logs
docker logs qwen-api

# Verify GPU access
docker run --gpus all nvidia/cuda:12.6.0-runtime-ubuntu22.04 nvidia-smi

# Check port availability
netstat -tuln | grep 8000
```

### Log Analysis

Key log patterns:
```bash
# Service ready
"Qwen Image Edit Nunchanku API is running"

# Model loaded
"Image edit service initialized successfully"

# GPU info
"GPU Memory Info: {...}"

# Error patterns
"CUDA out of memory"
"Failed to initialize image edit service"
"Model loading failed"
```

## Scaling and Load Balancing

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  qwen-api:
    scale: 3  # Run 3 instances
  
  nginx:
    # Load balancer configuration
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
```

### Vertical Scaling

```bash
# Increase container resources
docker run --gpus all \
  --memory=32g \
  --cpus=8 \
  qwen-image-edit-api
```

## Backup and Recovery

### Model Cache Backup

```bash
# Backup models
tar -czf models-backup-$(date +%Y%m%d).tar.gz models/

# Restore models
tar -xzf models-backup-20241201.tar.gz
```

### Configuration Backup

```bash
# Backup configuration
cp docker-compose.yml docker-compose.yml.bak
cp .env .env.bak
```

## Support

For deployment issues:

1. **Check the logs**: Always start with service logs
2. **Verify GPU access**: Ensure NVIDIA drivers and Docker GPU support
3. **Test with minimal config**: Start with basic Docker run command
4. **Monitor resources**: Check GPU memory, disk space, and network
5. **Documentation**: Refer to API docs at `/docs` endpoint

## Performance Benchmarks

### Expected Performance (RTX 4090)

| Configuration | Processing Time | GPU Memory | Quality |
|---------------|-----------------|------------|---------|
| 4 steps, rank=64 | 1.8s | 3.2GB | Good |
| 8 steps, rank=64 | 3.2s | 3.5GB | Better |
| 8 steps, rank=128 | 3.7s | 4.2GB | Best |

### Load Testing

```bash
# Use Apache Bench for load testing
ab -n 100 -c 10 -H "Content-Type: application/json" \
  -p test-payload.json \
  http://localhost:8000/edit-image
```