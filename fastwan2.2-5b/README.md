# FastWAN 2.2-5B ComfyUI Consolidated Docker

This Docker image provides a complete, ready-to-use ComfyUI installation with FastWAN 2.2-5B models and custom nodes pre-installed. Optimized for RTX 4090 GPU.

## Features

- **ComfyUI** with all dependencies pre-installed
- **FastWAN 2.2-5B models** included:
  - Diffusion model: `wan2.2_ti2v_5B_fp16.safetensors`
  - Text encoder: `umt5_xxl_fp8_e4m3fn_scaled.safetensors`
  - VAE: `wan2.2_vae.safetensors`
  - LoRA: `Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors`
- **FastWAN custom nodes** from FNGarvin/fastwan-moviegen
- **RTX 4090 optimizations** with proper CUDA settings
- **Caddy reverse proxy** for web access
- **Tailscale VPN** support for secure remote access
- **Optional Jupyter Lab** for development

## System Requirements

- **GPU**: NVIDIA RTX 4090 (or compatible CUDA GPU with 24GB+ VRAM)
- **RAM**: 32GB+ recommended
- **Storage**: 50GB+ free space for Docker image and models
- **Docker**: Version 20.10+ with NVIDIA Container Toolkit

## Quick Start

### 1. Build the Docker Image

```bash
cd /Users/sontl/workspace/runpod/comfyui/fastwan2.2-5b
docker build -f Dockerfile.consolidated -t fastwan-comfyui:latest .
```

**Note**: Initial build will take 30-60 minutes due to model downloads (~20GB total).

### 2. Run the Container

#### Basic Run (Local Access)
```bash
docker run -d \
  --name fastwan-comfyui \
  --gpus all \
  -p 8188:8188 \
  -v $(pwd)/workspace:/workspace/persistent \
  fastwan-comfyui:latest
```

#### Advanced Run (with Tailscale)
```bash
docker run -d \
  --name fastwan-comfyui \
  --gpus all \
  -p 8188:8188 \
  -e TAILSCALE_AUTHKEY="your-tailscale-auth-key" \
  -e RUNPOD_POD_HOSTNAME="fastwan-gpu-$(date +%s)" \
  -v $(pwd)/workspace:/workspace/persistent \
  fastwan-comfyui:latest
```

#### With Jupyter Lab
```bash
docker run -d \
  --name fastwan-comfyui \
  --gpus all \
  -p 8188:8188 \
  -p 8888:8888 \
  -e ENABLE_JUPYTER=true \
  -v $(pwd)/workspace:/workspace/persistent \
  fastwan-comfyui:latest
```

### 3. Access ComfyUI

- **ComfyUI Interface**: http://localhost:8188
- **Jupyter Lab** (if enabled): http://localhost:8888/jupyter/?token=runpod

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_LAUNCH_ARGS` | `--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto` | ComfyUI startup arguments |
| `ENABLE_JUPYTER` | `false` | Enable Jupyter Lab |
| `TAILSCALE_AUTHKEY` | - | Tailscale authentication key |
| `RUNPOD_POD_HOSTNAME` | `fastwan-comfy-pod` | Hostname for Tailscale |
| `CUDA_VISIBLE_DEVICES` | `0` | GPU device selection |
| `PYTORCH_CUDA_ALLOC_CONF` | `max_split_size_mb:512` | CUDA memory allocation |

## RTX 4090 Optimizations

The image includes several optimizations for RTX 4090:

- **FP8 Disabled**: `TORCH_INDUCTOR_FORCE_DISABLE_FP8=1` for Ampere compatibility
- **Memory Management**: Optimized CUDA memory allocation
- **Preview Method**: Auto-enabled for faster workflow feedback
- **SageAttention**: Pre-installed for improved attention performance

## Model Verification

The startup script automatically verifies all FastWAN models are present:

```bash
# Check container logs
docker logs fastwan-comfyui

# Should show:
# [services] ✓ All FastWAN 2.2-5B models verified successfully!
```

## Troubleshooting

### GPU Not Detected
```bash
# Verify NVIDIA runtime
docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi
```

### Out of Memory Errors
```bash
# Reduce batch size or use CPU fallback
docker run ... -e COMFY_LAUNCH_ARGS="--listen 0.0.0.0 --port 8188 --cpu" ...
```

### Model Download Issues
```bash
# Rebuild with better network
docker build --no-cache -f Dockerfile.consolidated -t fastwan-comfyui:latest .
```

### Container Won't Start
```bash
# Check logs
docker logs fastwan-comfyui

# Interactive debugging
docker run -it --rm --gpus all fastwan-comfyui:latest /bin/bash
```

## Development

### Custom Nodes
Mount your custom nodes directory:
```bash
docker run ... -v $(pwd)/custom_nodes:/workspace/ComfyUI/custom_nodes ...
```

### Model Storage
Mount external model directory:
```bash
docker run ... -v /path/to/models:/workspace/ComfyUI/models ...
```

### Using Alternative Startup Script
```bash
# Copy the consolidated startup script
docker run ... -v $(pwd)/start_services_consolidated.sh:/usr/local/bin/start_services.sh ...
```

## File Structure

```
/workspace/ComfyUI/
├── main.py                 # ComfyUI main application
├── models/
│   ├── diffusion_models/   # FastWAN diffusion model
│   ├── text_encoders/      # FastWAN text encoder
│   ├── vae/               # FastWAN VAE
│   └── loras/             # FastWAN LoRA
├── custom_nodes/
│   └── fastwan-moviegen/  # FastWAN custom nodes
└── requirements.txt       # Python dependencies
```

## Performance Tips

1. **Use SSD storage** for Docker volumes
2. **Allocate sufficient RAM** (32GB+ recommended)
3. **Monitor GPU temperature** during intensive workflows
4. **Use preview mode** for faster iteration
5. **Batch process** multiple images when possible

## Support

For issues related to:
- **FastWAN models**: Check [Comfy-Org/Wan_2.2_ComfyUI_Repackaged](https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged)
- **Custom nodes**: Check [FNGarvin/fastwan-moviegen](https://github.com/FNGarvin/fastwan-moviegen)
- **ComfyUI**: Check [comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)

## License

This Docker configuration is provided under CC BY-NC 4.0. Individual components maintain their respective licenses.
