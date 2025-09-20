# Qwen Image Edit ComfyUI - Network Storage Optimized

This is an optimized Docker setup for Qwen Image Edit using ComfyUI with Nunchaku optimization that downloads models from network storage at runtime, making deployment on Novita.ai much faster.

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
  -t ghcr.io/sontl/qwen-image-edit-v1:latest \
  -f qwen-image-edit-v1/Dockerfile \
  --push \
  qwen-image-edit-v1

docker build --tag ghcr.io/sontl/qwen-image-edit-v1:latest --push
  

# For local testing (without push)
docker buildx build \
  --platform linux/amd64 \
  -t qwen-image-edit-v1:latest \
  -f qwen-image-edit-v1/Dockerfile \
  --load \
  qwen-image-edit-v1
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
   - Pushes to `main` branch with changes in `qwen-image-edit-v1/`
   - Manual trigger via GitHub Actions UI

### Run Locally

```bash
docker run --gpus all -p 8188:8188 -p 8189:8189 \
  -v $(pwd)/models:/workspace/ComfyUI/models \
  qwen-image-edit-v1:latest
```

### Deploy on Novita.ai

1. Push your image to a registry:
```bash
docker tag qwen-image-edit-v1:latest your-registry/qwen-image-edit-v1:latest
docker push your-registry/qwen-image-edit-v1:latest
```

2. Create a new GPU instance on Novita.ai with:
   - **GPU**: RTX 4090
   - **Image**: `your-registry/qwen-image-edit-v1:latest`
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

The Qwen Image Edit API edits images using text prompts with advanced AI models.

### Edit Image

```bash
curl -X POST "http://localhost:8189/edit-image" \
  -H "Content-Type: application/json" \
  -d '{
    "image_url": "https://example.com/image.jpg",
    "prompt": "change the background to a beach scene",
    "negative_prompt": "blurry, low quality",
    "steps": 8,
    "cfg": 1.0,
    "megapixels": 1.0
  }'
```

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_url` | string | **Required** | URL to input image (JPG/PNG/WebP) |
| `prompt` | string | **Required** | Text description of desired edits |
| `negative_prompt` | string | "" | What to avoid in the edit |
| `seed` | integer | random | Random seed for generation |
| `steps` | integer | 8 | Number of diffusion steps |
| `cfg` | float | 1.0 | Classifier-free guidance scale |
| `megapixels` | float | 1.0 | Target image size in megapixels |

### Check Status

```bash
curl "http://localhost:8189/status/{job_id}"
```

### Download Edited Image

```bash
curl "http://localhost:8189/download/{job_id}" -o edited_image.png
```

### Example Response

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "message": "Image editing started"
}
```

### Status Values

- `queued`: Job is waiting to start
- `processing`: Video is being generated
- `completed`: Video is ready for download
- `error`: Generation failed

## Performance Tips

1. **Use Network Storage**: Mount a persistent volume to `/workspace/ComfyUI/models` to cache models between deployments
2. **Optimize Memory**: For RTX 4090, the default memory settings should work well
3. **Monitor Downloads**: First startup takes 5-10 minutes to download models (~8GB total)
4. **Subsequent Starts**: With cached models, startup takes ~30-60 seconds

## Model Downloads

The following models are downloaded automatically:

- **Qwen Model**: `svdq-int4_r128-qwen-image-lightningv1.1-8steps.safetensors` (~4GB)
- **CLIP**: `qwen_2.5_vl_7b_fp8_scaled.safetensors` (~7GB)
- **VAE**: `qwen_image_vae.safetensors` (~300MB)

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
qwen-image-edit-v1/
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

log "Step 2: Setting up InfiniteTalk custom node..."  
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
LOCKFILE="/tmp/InfiniteTalk_setup.lock"
if [ -f "$LOCKFILE" ]; then
    exit 0
fi
```

## Deployment Steps

### 1. Clean Rebuild
```bash
cd qwen-image-edit-v1

# Set your registry (optional)
export REGISTRY="your-dockerhub-username"

# Clean rebuild with no cache
./rebuild.sh
```

### 2. Deploy to Novita.ai
Use the new image tag: `your-registry/qwen-image-edit-v1:v2-fixed`

### 3. Expected Logs (Fixed)
```
[HH:MM:SS] === InfiniteTalk  Simple Startup ===
[HH:MM:SS] Step 1: Setting up ComfyUI...
[HH:MM:SS] Cloning ComfyUI...
[HH:MM:SS] Installing ComfyUI requirements...
[HH:MM:SS] Step 2: Setting up InfiniteTalk custom node...
[HH:MM:SS] Cloning InfiniteTalk custom node...
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

# Generate test video
curl -X POST "http://your-instance-ip:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A cat playing with yarn", "steps": 4}'
```

## Rollback Plan

If this still doesn't work, use the consolidated version:
```bash
# Use the working but larger image
cd ../InfiniteTalk
docker build -f Dockerfile.consolidated -t InfiniteTalk-consolidated .
```

The consolidated version includes all models in the image (~15GB) but is guaranteed to work.

## Support

The new simple script should resolve all the directory and race condition issues. If you still see problems, the logs will now be much clearer about what's failing.