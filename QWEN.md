# ComfyUI AI Services Workspace

This repository contains multiple AI service projects based on ComfyUI for various computer vision tasks, including image editing, video generation, and talking video synthesis. Each service is containerized using Docker with optimized network storage deployment strategies.

## Project Overview

The workspace contains several related AI services:

1. **qwen-image-edit-comfyui** - Image editing API using Qwen models with text prompts
2. **fastwan2.2-5b-network-storage** - Video generation from text prompts using FastWAN 2.2-5B model
3. **infinite-talk-v1** - Talking video generation from image and audio using InfiniteTalk
4. **wan2.2-14b-loras-v1** - Image-to-video conversion using WAN 2.2-14B models with LoRAs
5. **fastwan2.2-5b-packed** - Consolidated version of FastWAN with models pre-bundled

Each service follows a consistent architecture pattern with Docker containers, FastAPI APIs, and ComfyUI integration.

## Architecture & Structure

### Standard Project Structure
Each service follows this consistent layout:
```
project-name/
├── Dockerfile                        # Container definition
├── README.md                         # Project documentation
├── api_requirements.txt              # Python dependencies
├── api_wrapper.py                    # FastAPI application wrapper for ComfyUI
├── workflow_api.json                # ComfyUI workflow definition
├── Caddyfile                        # Reverse proxy configuration
├── build.sh                         # Docker build script
├── rebuild.sh                       # Clean rebuild script
├── start_services.sh                # Legacy startup script
├── start_services_simple.sh         # Simplified startup (preferred)
└── models/                          # Pydantic data models
```

### Two Deployment Strategies
1. **Network Storage** (Preferred): Lightweight images (~2-3GB) with models downloaded at runtime
2. **Consolidated**: Heavy images (~15-20GB) with models pre-bundled

### Service Types
1. **ComfyUI-based Services**: API wrapper pattern with WebSocket integration
2. **Direct API Services**: FastAPI applications interfacing directly with models

## Building and Running

### Prerequisites
- Docker with BuildKit enabled
- NVIDIA GPU with appropriate drivers
- At least 10GB free disk space (for network storage versions)
- Git LFS for large files

### Building Projects
```bash
# From a project directory (e.g., qwen-image-edit-comfyui)
cd qwen-image-edit-comfyui

# Create and use a new builder instance (only needed once)
docker buildx create --use

# Build for your platform
docker build -t qwen-image-edit:latest .

# Build for Linux/AMD64 from different platform
docker buildx build --platform linux/amd64 -t qwen-image-edit:latest --load .
```

### Running Services
```bash
# Run with GPU access
docker run --gpus all -p 8188:8188 -p 8189:8189 \
  -v $(pwd)/models:/workspace/ComfyUI/models \
  qwen-image-edit:latest
```

### API Endpoints
- `http://localhost:8188` - ComfyUI web interface
- `http://localhost:8189` - API wrapper endpoints

### Example API Usage (Qwen Image Edit)
```bash
curl -X POST "http://localhost:8189/edit-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "prompt": "change the background to a beach scene",
    "steps": 8,
    "cfg": 1.0
  }'
```

## Development Conventions

### Port Allocation
- 8000: Direct API services
- 8188: ComfyUI web interface
- 8189: API wrapper for ComfyUI services
- 8888: Jupyter Lab (when enabled)

### Environment Variables
- `ENABLE_FAST_DOWNLOAD`: Enable aria2c for parallel downloads
- `ENABLE_TAILSCALE`: Enable Tailscale networking
- `ENABLE_JUPYTER`: Enable JupyterLab
- `LOG_LEVEL`: Set logging verbosity

### Error Handling
- Centralized error handling in service wrappers
- Consistent error response formats
- Graceful degradation strategies

## Key Files and Components

1. **api_wrapper.py**: FastAPI wrapper that provides REST API for ComfyUI workflows
2. **workflow_api.json**: ComfyUI workflow definitions that connect AI model nodes
3. **start_services_simple.sh**: Simplified startup script that fixes race conditions
4. **Dockerfile**: Multi-stage Docker builds optimized for size and load times

## Performance Optimizations

- **Sequential execution**: Fixed race conditions by ensuring setup steps run sequentially
- **Fast downloads**: Uses aria2c with 16 parallel connections
- **Smart caching**: Checks if models exist before downloading
- **GPU optimization**: RTX 4090 tuned environment variables
- **Memory management**: Configured for optimal GPU memory usage

## Deployment Notes

### First Startup
- Network storage versions take 5-10 minutes to download models (~8GB total)
- Subsequent starts take ~30-60 seconds with cached models

### Cloud Deployment
The network storage versions are optimized for cloud deployments (like Novita.ai) where you frequently create/destroy instances.

### Model Downloads
Each project downloads specific models automatically:
- **Qwen Image Edit**: Qwen image editing models (~11GB total)
- **FastWAN**: Video generation models (~8GB total)
- **InfiniteTalk**: Talking video models (~8GB total)
- **WAN 2.2-14B**: High-quality image-to-video models (~17GB total)