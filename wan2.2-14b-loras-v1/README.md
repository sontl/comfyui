# WAN 2.2-14B LoRAs Image-to-Video - Optimized for Novita.ai

This is an optimized Docker setup for WAN 2.2-14B with LoRAs that converts input images to videos using advanced diffusion models. The setup downloads models from network storage at runtime, making deployment on Novita.ai much faster.

## Key Optimizations

- **Lightweight Image**: Only ~2-3GB vs 15-20GB for the consolidated version
- **Fast Downloads**: Uses aria2c with 16 parallel connections for model downloads
- **Parallel Setup**: Downloads models while setting up ComfyUI simultaneously
- **Smart Caching**: Checks if models exist before downloading
- **RTX 4090 Optimized**: Environment variables tuned for RTX 4090 performance

## Build Options

### Option 1: Local Build (Recommended for Large Images)

#### Prerequisites
- Docker Desktop with BuildKit enabled
- At least 10GB free disk space
- Git LFS (if cloning a repository with large files)

#### Build for Linux/AMD64 (from macOS/ARM)

```bash
# Navigate to the project root
cd /path/to/comfyui

# Create and use a new builder instance (only needed once)
docker buildx create --use

# Build for linux/amd64 and push to GitHub Container Registry (GHCR)
docker buildx build \
  --platform linux/amd64 \
  -t ghcr.io/sontl/wan2.2-14b-loras-v1:latest \
  -f wan2.2-14b-loras-v1/Dockerfile \
  --push \
  wan2.2-14b-loras-v1
  

# For local testing (without push)
docker buildx build \
  --platform linux/amd64 \
  -t wan2.2-14b-loras-v1:latest \
  -f wan2.2-14b-loras-v1/Dockerfile \
  --load \
  wan2.2-14b-loras-v1
```

### Option 2: GitHub Actions Build

#### Prerequisites
- GitHub repository with the code
- GitHub Container Registry (GHCR) access
- Sufficient storage space (4GB+ per image version)

#### Setup
1. Ensure your repository has the workflow file at `.github/workflows/build-and-push.yml`
2. In GitHub repository settings, go to:
   - Settings > Actions > General
   - Under "Workflow permissions", enable "Read and write permissions"
   - Check "Allow GitHub Actions to create and approve pull requests"

3. The workflow will automatically run on:
   - Pushes to `main` branch with changes in `wan2.2-14b-loras-v1/`
   - Manual trigger via GitHub Actions UI

### Run Locally

```bash
docker run --gpus all -p 8188:8188 -p 8189:8189 \
  -v $(pwd)/models:/workspace/ComfyUI/models \
  wan2.2-14b-loras-v1:latest
```

### Deploy on Novita.ai

1. Push your image to a registry:
```bash
docker tag wan2.2-14b-loras-v1:latest your-registry/wan2.2-14b-loras-v1:latest
docker push your-registry/wan2.2-14b-loras-v1:latest
```

2. Create a new GPU instance on Novita.ai with:
   - **GPU**: RTX 4090
   - **Image**: `your-registry/wan2.2-14b-loras-v1:latest`
   - **Ports**: 8188, 8189
   - **Storage**: Mount network storage to `/workspace/ComfyUI/models` (optional for caching)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_FAST_DOWNLOAD` | `true` | Use aria2c for parallel downloads |
| `ENABLE_TAILSCALE` | `false` | Enable Tailscale networking |
| `TAILSCALE_AUTHKEY` | - | Tailscale auth key |
| `ENABLE_JUPYTER` | `false` | Enable JupyterLab |
| `COMFY_LAUNCH_ARGS` | See script | ComfyUI launch arguments |

## API Usage

### Generate Video from Image

```bash
curl -X POST "http://localhost:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/path/to/image.jpg",
    "prompt": "the girl is looking to the phone and feel happy, then she jump very happy",
    "negative_prompt": "slow, slow motion, 色调艳丽，过曝，静态，细节模糊不清",
    "steps": 6,
    "cfg_high_noise": 3.5,
    "cfg_low_noise": 3.5,
    "width": 640,
    "height": 640,
    "frames": 81,
    "fps": 16,
    "seed": 1
  }'
```

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_url` | string (URL) | **Required** | URL of the input image to animate |
| `prompt` | string | **Required** | Text description of the desired animation |
| `negative_prompt` | string | Default provided | What to avoid in the animation |
| `steps` | integer | 6 | Number of diffusion steps (higher = better quality, slower) |
| `cfg_high_noise` | float | 3.5 | CFG scale for high noise model |
| `cfg_low_noise` | float | 3.5 | CFG scale for low noise model |
| `width` | integer | 640 | Output video width (will be resized to this) |
| `height` | integer | 640 | Output video height (will be resized to this) |
| `frames` | integer | 81 | Number of frames in output video |
| `fps` | integer | 16 | Frames per second of output video |
| `seed` | integer | 1 | Random seed for reproducible results |

### Check Status

```bash
curl "http://localhost:8189/status/{job_id}"
```

### Download Video

```bash
curl "http://localhost:8189/download/{job_id}" -o video.mp4
```

## Performance Tips

1. **Use Network Storage**: Mount a persistent volume to `/workspace/ComfyUI/models` to cache models between deployments
2. **Optimize Memory**: For RTX 4090, the default memory settings should work well
3. **Monitor Downloads**: First startup takes 5-10 minutes to download models (~8GB total)
4. **Subsequent Starts**: With cached models, startup takes ~30-60 seconds

## Model Downloads

The following models are downloaded automatically:

- **High Noise Model**: `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors` (~7GB)
- **Low Noise Model**: `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors` (~7GB)
- **Text Encoder**: `umt5_xxl_fp16.safetensors` (~2GB)
- **VAE**: `wan_2.1_vae.safetensors` (~300MB)
- **LoRAs**: 
  - `high_noise_model.safetensors` (~500MB)
  - `low_noise_model.safetensors` (~500MB)

## Troubleshooting

### Slow Downloads
- Ensure `ENABLE_FAST_DOWNLOAD=true`
- Check network connectivity to HuggingFace
- Consider using a mirror or CDN

### Out of Memory
- Reduce batch size in workflow
- Lower video resolution/length
- Check GPU memory usage

### Models Not Found
- Check `/workspace/ComfyUI/models` directory structure
- Verify download completion in logs
- Manually download models if needed

## File Structure

```
wan2.2-14b-loras-v1/
├── Dockerfile                    # Optimized Docker image
├── start_services.sh            # Original startup script
├── start_services_consolidated.sh # Optimized startup script
├── api_wrapper.py               # FastAPI wrapper
├── workflow_api.json            # ComfyUI workflow
├── Caddyfile                    # Reverse proxy config
└── README.md                    # This file
```

## Comparison with Consolidated Version

| Aspect | Network Storage | Consolidated |
|--------|----------------|--------------|
| Image Size | ~2-3GB | ~15-20GB |
| First Startup | 5-10 min | 30-60 sec |
| Subsequent Starts | 30-60 sec | 30-60 sec |
| Network Usage | High (first time) | Low |
| Storage Efficiency | High | Low |
| Deployment Speed | Fast | Slow |

The network storage version is ideal for cloud deployments where you frequently create/destroy instances, while the consolidated version is better for long-running deployments.

## Fixes and Improvements

### Problem Analysis
The original startup script had several issues:
1. ComfyUI directory already existing but being empty
2. Git clone failing when directory exists
3. Multiple script instances running simultaneously
4. Script exiting on first error
5. Parallel processes causing race conditions
6. Docker layer caching issues
7. Old images being used
8. Registry not updated

### Solution: Complete Rebuild

We've created a **simple, bulletproof startup script** (`start_services_simple.sh`) that:

✅ **Sequential execution** - No parallel processes causing race conditions  
✅ **Robust directory handling** - Removes broken directories before cloning  
✅ **Alternative clone method** - Fallback if direct clone fails  
✅ **Clear logging** - Easy to debug what's happening  
✅ **Instance locking** - Prevents multiple startups  
✅ **Better error handling** - Continues with warnings instead of exiting on first error

### Key Differences in New Script

#### Old (Problematic)
```bash
# Parallel setup causing race conditions
setup_comfyui &
SETUP_PID=$!
download_models_parallel &
DOWNLOAD_PID=$!
```

#### New (Fixed)
```bash
# Sequential, step-by-step
log "Step 1: Setting up ComfyUI..."
# Setup ComfyUI completely first

log "Step 2: Setting up FastWAN custom node..."  
# Then setup custom nodes

log "Step 3: Downloading models..."
# Then download models one by one

log "Step 4: Starting services..."
# Finally start services
```

### Better Directory Handling
```bash
# Always ensure we have a clean setup
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    # Clean up any existing directory
    if [ -d "${COMFY_DIR}" ]; then
        rm -rf "${COMFY_DIR}"
    fi
    # Then clone fresh
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}"
fi
```

### Instance Lock
```bash
# Prevent multiple instances
LOCKFILE="/tmp/fastwan_setup.lock"
if [ -f "$LOCKFILE" ]; then
    exit 0
fi
```

## Deployment Steps

### 1. Clean Rebuild
```bash
cd wan2.2-14b-loras-v1

# Set your registry (optional)
export REGISTRY="your-dockerhub-username"

# Clean rebuild with no cache
./rebuild.sh
```

### 2. Deploy to Novita.ai
Use the new image tag: `your-registry/wan2.2-14b-loras-v1:v2-fixed`

### 3. Expected Logs (Fixed)
```
[HH:MM:SS] === FastWAN 2.2-5B Simple Startup ===
[HH:MM:SS] Step 1: Setting up ComfyUI...
[HH:MM:SS] Cloning ComfyUI...
[HH:MM:SS] Installing ComfyUI requirements...
[HH:MM:SS] Step 2: Setting up FastWAN custom node...
[HH:MM:SS] Cloning FastWAN custom node...
[HH:MM:SS] Step 3: Downloading models...
[HH:MM:SS] Model already exists: wan2.2_ti2v_5B_fp16.safetensors
[HH:MM:SS] Step 4: Starting services...
[HH:MM:SS] Starting API wrapper...
[HH:MM:SS] API wrapper started (PID: 123)
[HH:MM:SS] Starting ComfyUI...
[HH:MM:SS] ComfyUI started (PID: 456)
[HH:MM:SS] === Startup Complete ===
[HH:MM:SS] ComfyUI: http://localhost:8188
[HH:MM:SS] API: http://localhost:8189
```

## What's Different

| Aspect | Old Script | New Script |
|--------|------------|------------|
| Execution | Parallel (race conditions) | Sequential (reliable) |
| Error Handling | `set -e` (exit on error) | Continues with warnings |
| Directory Handling | Basic check | Robust cleanup & fallback |
| Logging | Mixed messages | Clear step-by-step |
| Instance Control | Complex lockfile | Simple PID lock |

## Verification

After deployment, check:

1. **No git errors**: No "destination path already exists" messages
2. **Clean startup**: Sequential step messages  
3. **Services running**: Both ComfyUI and API respond
4. **No restarts**: Container stays running without crashes

## Test API
```bash
# Health check
curl http://your-instance-ip:8189/

# Generate test video from image
curl -X POST "http://your-instance-ip:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/portrait.jpg",
    "prompt": "person smiling and waving at camera",
    "steps": 6
  }'
```

## Rollback Plan

If this still doesn't work, use the consolidated version:
```bash
# Use the working but larger image
cd ../fastwan2.2-5b
docker build -f Dockerfile.consolidated -t fastwan-consolidated .
```

The consolidated version includes all models in the image (~15GB) but is guaranteed to work.

## Support

The new simple script should resolve all the directory and race condition issues. If you still see problems, the logs will now be much clearer about what's failing.