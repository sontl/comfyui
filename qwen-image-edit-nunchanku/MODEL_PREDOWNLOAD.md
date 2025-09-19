# Model Pre-downloading in Docker

## Overview

The Dockerfile has been enhanced to pre-download all necessary models during the Docker image build process. This significantly improves startup time and ensures the API is ready to use immediately when the container starts.

## Pre-downloaded Models

### Base Model
- **Qwen/Qwen-Image-Edit**: The base Qwen Image Edit model from HuggingFace
- **Location**: `/app/models/Qwen--Qwen-Image-Edit/`

### Nunchaku Quantized Models
The following quantized models are pre-downloaded for optimal performance (r128 only):

#### Lightning Models (Fast Inference)
- `svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors` (8-step, rank 128)

#### Original Models
- `svdq-int4_r128-qwen-image-edit.safetensors` (rank 128)

**Location**: `/app/models/nunchaku-qwen-image-edit/`

## Benefits

### 1. Faster Startup
- No model downloading during container startup
- API is ready to serve requests immediately
- Reduced cold start time

### 2. Offline Operation
- Models are available locally
- No dependency on external network for model access
- Improved reliability in production environments

### 3. Consistent Performance
- Predictable model availability
- No download failures during runtime
- Consistent API response times

## Model Selection Logic

The API automatically selects the best available model based on:

1. **Local Cache Priority**: Always tries local pre-downloaded models first
2. **Rank Selection**: Only rank 128 is supported (optimal quality)
3. **Steps Selection**: Prefers 8-step lightning models for best balance of speed and quality
4. **Fallback**: Downloads from HuggingFace if local models are not available

## Verification

### During Build
The Docker build process includes model verification:
```bash
MODEL_CACHE_DIR=/app/models python3 verify_models.py
```

### Runtime Verification
You can verify models are available in a running container:
```bash
# List all downloaded models
python3 verify_models.py --list

# Verify model integrity
python3 verify_models.py
```

## Configuration

### Environment Variables
- `MODEL_CACHE_DIR`: Directory where models are stored (default: `/app/models`)

### Model Configuration
The API automatically detects available models and updates its configuration:
- `supported_ranks`: [128] (only rank 128 supported)
- `supported_steps`: Based on available lightning models
- `default_rank`: 128 (fixed)
- `default_steps`: 8 (preferred for quality)

## Storage Requirements

### Estimated Sizes
- Base Qwen Model: ~5-7 GB
- Nunchaku Lightning Model (r128, 8-step): ~1-2 GB
- Nunchaku Original Model (r128): ~1-2 GB
- Total: ~8-11 GB (significantly reduced from previous ~15-20 GB)

### Optimization
- Models use int4 quantization for reduced size
- Efficient safetensors format
- No duplicate model weights

## Troubleshooting

### Missing Models
If some models fail to download during build:
- The API will still work with available models
- Check build logs for download errors
- Verify network connectivity during build

### Runtime Issues
```bash
# Check available models
python3 verify_models.py

# Check model configuration
curl http://localhost:8000/model-info
```

### Manual Model Download
If needed, you can manually download models:
```python
from huggingface_hub import hf_hub_download

# Download specific model (r128 only)
hf_hub_download(
    repo_id="nunchaku-tech/nunchaku-qwen-image-edit",
    filename="svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors",
    cache_dir="/app/models",
    local_dir="/app/models/nunchaku-qwen-image-edit"
)
```

## Performance Impact

### Build Time
- Increased Docker build time (~10-15 minutes additional)
- One-time cost for significant runtime benefits

### Runtime Performance
- Near-instant model loading
- No network latency for model access
- Consistent inference performance

## Best Practices

1. **Build Optimization**: Use Docker layer caching to avoid re-downloading models
2. **Storage**: Ensure sufficient disk space for the Docker image
3. **Network**: Stable internet connection during build for reliable downloads
4. **Monitoring**: Use the verification script to ensure model integrity