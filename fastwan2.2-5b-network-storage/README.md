# FastWAN 2.2-5B Network Storage - Optimized for Novita.ai

This is an optimized Docker setup for FastWAN 2.2-5B that downloads models from network storage at runtime, making deployment on Novita.ai much faster.

## Key Optimizations

- **Lightweight Image**: Only ~2-3GB vs 15-20GB for the consolidated version
- **Fast Downloads**: Uses aria2c with 16 parallel connections for model downloads
- **Parallel Setup**: Downloads models while setting up ComfyUI simultaneously
- **Smart Caching**: Checks if models exist before downloading
- **RTX 4090 Optimized**: Environment variables tuned for RTX 4090 performance

## Quick Start

### Build the Docker Image

```bash
cd fastwan2.2-5b-network-storage
docker build -t fastwan-network:latest .
```

### Run Locally

```bash
docker run --gpus all -p 8188:8188 -p 8189:8189 \
  -v $(pwd)/models:/workspace/ComfyUI/models \
  fastwan-network:latest
```

### Deploy on Novita.ai

1. Push your image to a registry:
```bash
docker tag fastwan-network:latest your-registry/fastwan-network:latest
docker push your-registry/fastwan-network:latest
```

2. Create a new GPU instance on Novita.ai with:
   - **GPU**: RTX 4090
   - **Image**: `your-registry/fastwan-network:latest`
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

### Generate Video

```bash
curl -X POST "http://localhost:8189/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A cat playing with a ball of yarn",
    "steps": 8,
    "cfg": 1.0,
    "width": 1280,
    "height": 704,
    "length": 121,
    "fps": 24
  }'
```

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

- **Diffusion Model**: `wan2.2_ti2v_5B_fp16.safetensors` (~5GB)
- **Text Encoder**: `umt5_xxl_fp8_e4m3fn_scaled.safetensors` (~2GB)
- **VAE**: `wan2.2_vae.safetensors` (~300MB)
- **LoRA**: `Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors` (~500MB)

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
fastwan2.2-5b-network-storage/
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