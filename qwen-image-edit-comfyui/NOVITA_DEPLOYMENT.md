# Qwen Image Edit Deployment Guide for Novita.ai

This guide provides step-by-step instructions for deploying Qwen Image Edit with Nunchaku optimization on Novita.ai with optimal performance and cost efficiency.

## Prerequisites

1. Docker installed locally
2. Novita.ai account with GPU credits
3. Docker registry access (Docker Hub, GitHub Container Registry, etc.)

## Step 1: Build and Push Image

### Option A: Using the build script

```bash
cd qwen-image-edit-comfyui
export REGISTRY="your-dockerhub-username"  # or your registry
./build.sh
```

### Option B: Manual build and push

```bash
cd qwen-image-edit-comfyui

# Build the image
docker build -t qwen-image-edit:latest .

# Tag for your registry
docker tag qwen-image-edit:latest your-registry/qwen-image-edit:latest

# Push to registry
docker push your-registry/qwen-image-edit:latest
```

## Step 2: Deploy on Novita.ai

### Recommended Configuration

1. **GPU**: RTX 4090 (24GB VRAM)
2. **CPU**: 8+ cores
3. **RAM**: 32GB+
4. **Storage**: 50GB+ SSD
5. **Image**: `your-registry/qwen-image-edit:latest`

### Environment Variables

Set these in Novita.ai dashboard:

```bash
# Core settings
TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
CUDA_VISIBLE_DEVICES=0
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512

# Optional optimizations
ENABLE_FAST_DOWNLOAD=true
ENABLE_TAILSCALE=false
ENABLE_JUPYTER=false
```

### Port Configuration

Expose these ports:
- **8188**: ComfyUI Web Interface
- **8189**: FastAPI REST API

### Storage Configuration (Recommended)

Mount a persistent volume to `/workspace/ComfyUI/models` to cache models between deployments:

- **Mount Point**: `/workspace/ComfyUI/models`
- **Size**: 20GB+ (for model caching)
- **Type**: SSD for best performance

## Step 3: First Deployment

### Expected Timeline

1. **Image Pull**: 2-5 minutes (depending on network)
2. **Container Start**: 30 seconds
3. **Model Downloads**: 5-10 minutes (first time only)
4. **Service Ready**: Total ~7-15 minutes

### Monitoring Startup

Check the logs for these key messages:

```
[HH:MM:SS] === qwenImageEdit Simple Startup ===
[HH:MM:SS] Step 1: Verifying ComfyUI installation...
[HH:MM:SS] Step 2: Starting parallel model downloads...
[HH:MM:SS] ⬇ Starting download: Qwen Nunchaku Model
[HH:MM:SS] ✓ Downloaded: VAE Model
[HH:MM:SS] Step 3: Starting services...
[HH:MM:SS] === Startup Complete ===
[HH:MM:SS] ComfyUI: http://localhost:8188
[HH:MM:SS] API: http://localhost:8189
```

## Step 4: Verify Deployment

### Health Check

```bash
# Check API health
curl http://your-instance-ip:8189/

# Expected response:
# {"message":"Qwen Image Edit API","status":"running"}
```

### Test Image Editing

```bash
curl -X POST "http://your-instance-ip:8189/edit-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
    "prompt": "change the background to a beautiful sunset",
    "steps": 8,
    "cfg": 1.0,
    "megapixels": 1.0
  }'
```

## Step 5: Subsequent Deployments

With models cached in persistent storage:

1. **Image Pull**: 2-5 minutes (if updated)
2. **Container Start**: 30 seconds
3. **Model Check**: 10-30 seconds (cached models)
4. **Service Ready**: Total ~3-6 minutes

## Cost Optimization Tips

### 1. Use Persistent Storage
- Mount `/workspace/ComfyUI/models` to avoid re-downloading models
- Saves 5-10 minutes per deployment
- Reduces bandwidth costs

### 2. Instance Management
- Stop instances when not in use
- Use spot instances if available
- Monitor GPU utilization

### 3. Batch Processing
- Process multiple videos in one session
- Use the API to queue multiple jobs
- Maximize GPU utilization

## Performance Tuning

### For RTX 4090

The default settings are optimized for RTX 4090:

```bash
TORCH_INDUCTOR_FORCE_DISABLE_FP8=1
CUDA_VISIBLE_DEVICES=0
PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:512
```

### Memory Optimization

If you encounter OOM errors:

1. Reduce image size: `"megapixels": 0.5` (instead of 1.0)
2. Lower steps: `"steps": 4-6`
3. Enable CPU offloading in the model loader

### Speed Optimization

For faster generation:
1. Use fewer steps: `"steps": 4-6`
2. Lower CFG: `"cfg": 0.5-1.0`
3. Reduce image resolution with megapixels parameter

## Troubleshooting

### Common Issues

#### 1. Slow Model Downloads
```bash
# Check if aria2c is working
docker logs your-container-id | grep aria2c

# If failing, it will fallback to curl
# Consider using a mirror or CDN
```

#### 2. Out of Memory
```bash
# Check GPU memory usage
nvidia-smi

# Reduce video parameters or restart container
```

#### 3. Models Not Loading
```bash
# Check model directory
docker exec -it your-container-id ls -la /workspace/ComfyUI/models/

# Verify model files are complete
docker exec -it your-container-id find /workspace/ComfyUI/models/ -name "*.safetensors" -exec ls -lh {} \;
```

### Log Analysis

Key log patterns to watch:

```bash
# Successful model download
"Successfully downloaded: models/..."

# Service startup
"Startup complete!"

# API ready
"API available at: http://localhost:8189"

# Error patterns
"Failed to download"
"CUDA out of memory"
"Connection refused"
```

## API Documentation

Once deployed, access the interactive API documentation at:
`http://your-instance-ip:8189/docs`

This provides a complete interface for testing and integrating with the Qwen Image Edit API.

## Support

For issues specific to this deployment:
1. Check the container logs first
2. Verify GPU availability with `nvidia-smi`
3. Test with smaller video parameters
4. Ensure sufficient disk space for models

For Novita.ai platform issues, contact their support team.