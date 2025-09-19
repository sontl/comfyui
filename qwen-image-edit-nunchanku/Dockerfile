# syntax=docker/dockerfile:1.4
###############################################################################
# QWEN IMAGE EDIT NUNCHANKU API DOCKERFILE
# Optimized Docker image for Qwen Image Edit Nunchanku API service
###############################################################################

###############################################################################
# BUILD STAGE #################################################################
###############################################################################
ARG CUDA_VERSION=12.6.0
ARG UBUNTU_VERSION=22.04
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_VERSION} AS builder

# --- Base tooling -----------------------------------------------------------
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-venv python3-distutils python3-pip \
        build-essential git curl ca-certificates aria2 && \
    rm -rf /var/lib/apt/lists/*

# --- Python venv & Core ML stack ---------------------------------------------
ARG TORCH_CUDA=cu126
ARG TORCH_VER=2.7.0
ARG TVISION_VER=0.22.0+${TORCH_CUDA}
ARG TAUDIO_VER=2.7.0+${TORCH_CUDA}
ARG XFORMERS_VER=0.0.30

ENV VENV_PATH=/opt/venv
RUN python3 -m venv ${VENV_PATH} && \
    . ${VENV_PATH}/bin/activate && \
    pip install --upgrade --no-cache-dir pip setuptools wheel && \
    pip install --extra-index-url https://download.pytorch.org/whl/${TORCH_CUDA} \
        torch==${TORCH_VER}+${TORCH_CUDA} \
        torchvision==${TVISION_VER} \
        torchaudio==${TAUDIO_VER} \
        xformers==${XFORMERS_VER} && \
    find ${VENV_PATH} -name '__pycache__' -type d -exec rm -rf {} + && \
    pip cache purge

# Install Nunchaku wheel
RUN . ${VENV_PATH}/bin/activate && \
    pip install --no-cache-dir "https://github.com/nunchaku-tech/nunchaku/releases/download/v0.3.1/nunchaku-0.3.1+torch2.7-cp310-cp310-linux_x86_64.whl"

# Install diffusers from GitHub repo
RUN . ${VENV_PATH}/bin/activate && \
    pip install --no-cache-dir git+https://github.com/huggingface/diffusers.git && \
    find ${VENV_PATH} -name '__pycache__' -type d -exec rm -rf {} + && \
    pip cache purge

# Install API dependencies
COPY api_requirements.txt /tmp/
RUN . ${VENV_PATH}/bin/activate && \
    pip install --no-cache-dir -r /tmp/api_requirements.txt && \
    find ${VENV_PATH} -name '__pycache__' -type d -exec rm -rf {} + && \
    pip cache purge

# --- Pre-download Nunchaku quantized models -----------------------------------
# Create model cache directory
RUN mkdir -p /app/models/nunchaku-qwen-image-edit

# Download base Qwen Image Edit model
RUN . ${VENV_PATH}/bin/activate && \
    python3 -c "
from huggingface_hub import snapshot_download
import os
print('Downloading base Qwen Image Edit model...')
snapshot_download(
    repo_id='Qwen/Qwen-Image-Edit',
    cache_dir='/app/models',
    local_dir='/app/models/Qwen--Qwen-Image-Edit',
    local_dir_use_symlinks=False
)
print('Base model download completed')
"

# Download Nunchaku quantized models (r128 only, 8-step and original)
RUN . ${VENV_PATH}/bin/activate && \
    python3 -c "
from huggingface_hub import hf_hub_download
import os

# Model configurations to download (r128 only, no 4-step models)
models = [
    # 8-step model (r128 only)
    ('nunchaku-tech/nunchaku-qwen-image-edit', 'svdq-int4_r128-qwen-image-edit-lightningv1.0-8steps.safetensors'),
    # Original model (r128 only)
    ('nunchaku-tech/nunchaku-qwen-image-edit', 'svdq-int4_r128-qwen-image-edit.safetensors'),
]

cache_dir = '/app/models'
os.makedirs(cache_dir, exist_ok=True)

for repo_id, filename in models:
    try:
        print(f'Downloading {filename}...')
        hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            cache_dir=cache_dir,
            local_dir=f'{cache_dir}/nunchaku-qwen-image-edit',
            local_dir_use_symlinks=False
        )
        print(f'Downloaded {filename}')
    except Exception as e:
        print(f'Warning: Failed to download {filename}: {e}')
        continue

print('Nunchaku model downloads completed')
"

# Verify downloaded models
COPY verify_models.py /tmp/
RUN . ${VENV_PATH}/bin/activate && \
    cd /tmp && \
    MODEL_CACHE_DIR=/app/models python3 verify_models.py && \
    echo "Model verification completed"

###############################################################################
# RUNTIME STAGE ###############################################################
###############################################################################
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-runtime-ubuntu${UBUNTU_VERSION}

# Install runtime system dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-dev git curl ca-certificates tini \
        ffmpeg libsm6 libxext6 libxrender-dev libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built Python virtual environment
ENV VENV_PATH=/opt/venv
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Copy application code
WORKDIR /app
COPY main.py /app/
COPY models/ /app/models/
COPY services/ /app/services/
COPY utils/ /app/utils/
COPY api_requirements.txt /app/
COPY start_qwen_api.sh /app/
COPY verify_models.py /app/
RUN chmod +x /app/start_qwen_api.sh

# Set environment variables optimized for Qwen Image Edit
ENV PATH="${VENV_PATH}/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app:${PYTHONPATH}" \
    # GPU optimizations
    CUDA_VISIBLE_DEVICES="0" \
    PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512" \
    TORCH_INDUCTOR_FORCE_DISABLE_FP8="1" \
    # API settings
    API_HOST="0.0.0.0" \
    API_PORT="8000" \
    MODEL_CACHE_DIR="/app/models" \
    LOG_LEVEL="INFO" \
    ENVIRONMENT="production"

# Create model cache directory
RUN mkdir -p /app/models

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Use tini as the entrypoint to properly manage processes
ENTRYPOINT ["/usr/bin/tini", "-s", "--", "/app/start_qwen_api.sh"]