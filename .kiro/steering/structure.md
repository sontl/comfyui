# Project Structure & Organization

## Repository Layout

The repository follows a multi-project structure with each AI service in its own directory:

```
├── fastwan2.2-5b-network-storage/    # FastWAN video generation (network storage)
├── fastwan2.2-5b-packed/             # FastWAN video generation (consolidated)
├── infinite-talk-v1/                 # Talking video generation
├── qwen-image-edit-nunchanku/         # Image editing API
├── wan2.2-14b-loras-v1/              # Enhanced video generation with LoRAs
├── .github/                          # GitHub Actions workflows
├── .kiro/                            # Kiro AI assistant configuration
└── .qoder/                           # Quest documentation
```

## Standard Project Structure

Each service project follows this consistent structure:

```
project-name/
├── Dockerfile                        # Container definition
├── README.md                         # Project documentation
├── api_requirements.txt              # Python dependencies
├── api_wrapper.py                    # FastAPI application (ComfyUI projects)
├── main.py                          # FastAPI application (direct API projects)
├── workflow_api.json                # ComfyUI workflow definition
├── Caddyfile                        # Reverse proxy configuration
├── build.sh                         # Docker build script
├── rebuild.sh                       # Clean rebuild script
├── start_services.sh                # Service startup script
├── start_services_simple.sh         # Simplified startup (preferred)
├── models/                          # Pydantic data models (API projects)
│   ├── __init__.py
│   └── api_models.py
├── services/                        # Business logic services
│   ├── __init__.py
│   └── *_service.py
├── utils/                           # Utility modules
│   ├── __init__.py
│   ├── error_handler.py
│   ├── gpu_utils.py
│   ├── image_processor.py
│   ├── logger.py
│   └── model_utils.py
└── tests/                           # Test suite
    ├── __init__.py
    └── test_*.py
```

## File Naming Conventions

### Python Files
- `main.py`: FastAPI application entry point
- `api_wrapper.py`: ComfyUI integration wrapper
- `*_service.py`: Business logic services
- `*_utils.py`: Utility modules
- `api_models.py`: Pydantic request/response models
- `test_*.py`: Test files

### Configuration Files
- `Dockerfile`: Container definition
- `api_requirements.txt`: Python dependencies
- `workflow_api.json`: ComfyUI workflow
- `Caddyfile`: Reverse proxy config
- `pytest.ini`: Test configuration

### Scripts
- `build.sh`: Standard Docker build
- `rebuild.sh`: Clean rebuild with `--no-cache`
- `start_services.sh`: Legacy startup script
- `start_services_simple.sh`: Preferred startup script

## Architecture Patterns

### Two Deployment Strategies

1. **Network Storage** (Preferred for cloud):
   - Lightweight Docker images (~2-3GB)
   - Models downloaded at runtime
   - Fast deployment, slower first startup
   - Examples: `fastwan2.2-5b-network-storage/`, `infinite-talk-v1/`

2. **Consolidated** (For persistent deployments):
   - Heavy Docker images (~15-20GB)
   - Models baked into image
   - Slow deployment, fast startup
   - Examples: `fastwan2.2-5b-packed/`

### Service Types

1. **ComfyUI-based Services**:
   - Use `api_wrapper.py` for REST API
   - WebSocket integration for real-time updates
   - Workflow-based processing
   - Examples: FastWAN, InfiniteTalk

2. **Direct API Services**:
   - Use `main.py` with FastAPI
   - Direct model integration
   - Optimized inference pipelines
   - Examples: Qwen Image Edit

## Code Organization Principles

### Modular Design
- Separate concerns: API, business logic, utilities
- Reusable components across projects
- Clear dependency injection patterns

### Error Handling
- Centralized error handling in `utils/error_handler.py`
- Consistent error response formats
- Graceful degradation strategies

### Configuration Management
- Environment variable-based configuration
- Sensible defaults for all parameters
- Runtime configuration updates where applicable

### Testing Structure
- Unit tests for individual components
- Integration tests for API endpoints
- Performance tests for GPU operations
- Mock external dependencies

## Docker Patterns

### Multi-stage Builds
```dockerfile
# Build stage: Install dependencies
FROM nvidia/cuda:12.6.0-cudnn-devel-ubuntu22.04 AS builder

# Runtime stage: Minimal runtime environment
FROM nvidia/cuda:12.6.0-cudnn-runtime-ubuntu22.04
```

### Layer Optimization
- System dependencies first (rarely change)
- Python dependencies second (change occasionally)
- Application code last (changes frequently)

### Health Checks
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8188/ || exit 1
```

## Port Conventions

- `8000`: Direct API services (Qwen Image Edit)
- `8188`: ComfyUI web interface
- `8189`: API wrapper for ComfyUI services
- `8888`: Jupyter Lab (when enabled)

## Environment Standards

### Required Variables
- `CUDA_VISIBLE_DEVICES`: GPU selection
- `PYTORCH_CUDA_ALLOC_CONF`: Memory management

### Optional Variables
- `ENABLE_FAST_DOWNLOAD`: Use aria2c for downloads
- `ENABLE_TAILSCALE`: VPN networking
- `ENABLE_JUPYTER`: Development environment
- `LOG_LEVEL`: Logging verbosity