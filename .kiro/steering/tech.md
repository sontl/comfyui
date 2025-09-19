# Technology Stack & Build System

## Core Technologies

### Backend Framework
- **FastAPI**: Primary web framework for REST APIs
- **Uvicorn**: ASGI server for FastAPI applications
- **WebSocket**: Real-time communication for ComfyUI integration
- **Pydantic**: Data validation and serialization

### AI/ML Stack
- **PyTorch**: Deep learning framework (≥2.5)
- **CUDA**: GPU acceleration (≥12.2)
- **ComfyUI**: Node-based UI for AI workflows
- **Nunchaku**: Optimized inference engine for Qwen models
- **Diffusers**: Hugging Face diffusion models library
- **Transformers**: Model loading and inference

### Infrastructure
- **Docker**: Containerization with multi-stage builds
- **NVIDIA Container Toolkit**: GPU support in containers
- **Caddy**: Reverse proxy and web server
- **Tailscale**: VPN networking (optional)
- **Aria2c**: Fast parallel downloads for models

### Image/Video Processing
- **Pillow (PIL)**: Image processing
- **OpenCV**: Computer vision operations
- **FFmpeg**: Video processing and encoding

## Build System

### Docker Build Commands

```bash
# Standard build
docker build -t <image-name>:latest .

# Multi-platform build (for ARM to AMD64)
docker buildx create --use
docker buildx build --platform linux/amd64 -t <image-name>:latest --push .

# Local testing build
docker buildx build --platform linux/amd64 -t <image-name>:latest --load .
```

### Common Scripts

Each project includes these standard scripts:
- `build.sh`: Standard Docker build
- `rebuild.sh`: Clean rebuild with no cache
- `start_services.sh`: Service startup script
- `start_services_simple.sh`: Simplified startup (preferred)

### Environment Variables

Standard environment variables across projects:
- `CUDA_VISIBLE_DEVICES=0`: GPU selection
- `PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512`: Memory optimization
- `TORCH_INDUCTOR_FORCE_DISABLE_FP8=1`: RTX 4090 compatibility
- `ENABLE_FAST_DOWNLOAD=true`: Use aria2c for downloads
- `COMFY_LAUNCH_ARGS`: ComfyUI startup parameters

## Development Workflow

### Testing Commands

```bash
# Python unit tests
pytest
pytest -m "not slow"  # Skip slow tests
pytest tests/test_api.py  # Specific test file

# API testing
curl http://localhost:8000/health  # Health check
curl -X POST http://localhost:8000/edit-image -d @test_request.json  # API test
```

### Local Development

```bash
# Python virtual environment setup
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -r api_requirements.txt

# Run locally
python main.py
```

### Docker Development

```bash
# Run with GPU support
docker run --gpus all -p 8000:8000 <image-name>:latest

# Run with volume mounts for development
docker run --gpus all -p 8000:8000 -v $(pwd):/app <image-name>:latest

# Debug container
docker run -it --rm --gpus all <image-name>:latest /bin/bash
```

## Performance Optimization

### GPU Memory Management
- Use CPU offloading for models >18GB VRAM
- Sequential CPU offloading for medium VRAM (8-18GB)
- Attention slicing for low VRAM (<8GB)

### Model Loading Strategy
- Lazy loading: Load models on first request
- Persistent caching: Cache models between container restarts
- Network storage: Download models at runtime for faster deployment

### Build Optimization
- Multi-stage Dockerfiles to reduce image size
- Layer caching for faster rebuilds
- Separate build and runtime stages