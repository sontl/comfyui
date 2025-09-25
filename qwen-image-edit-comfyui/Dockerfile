# syntax=docker/dockerfile:1.7
###############################################################################
# QWEN IMAGE EDIT DOCKERFILE
# Lightweight image that downloads models at runtime for fast deployment
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
        xformers==${XFORMERS_VER} \
        onnx==1.16.2 onnxruntime-gpu==1.22.0 numpy==1.26.4 && \
    # Install Nunchaku wheel
    pip install --no-cache-dir "https://github.com/nunchaku-tech/nunchaku/releases/download/v1.0.1dev20250924/nunchaku-1.0.1.dev20250924+torch2.7-cp310-cp310-linux_x86_64.whl" && \
    find ${VENV_PATH} -name '__pycache__' -type d -exec rm -rf {} + && \
    pip cache purge

# Install API dependencies
RUN . ${VENV_PATH}/bin/activate && \
    pip install --no-cache-dir \
        fastapi==0.104.1 \
        uvicorn==0.24.0 \
        websocket-client==1.6.4 \
        requests==2.31.0 \
        pydantic==2.5.0 \
        librosa==0.10.2  \
        opencv-python 


# --- ComfyUI Installation ---------------------------------------------------
WORKDIR /workspace
RUN git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI && \
    cd ComfyUI && \
    . ${VENV_PATH}/bin/activate && \
    pip install --no-cache-dir -r requirements.txt && \
    # Create model directories
    mkdir -p models/diffusion_models models/text_encoders models/vae models/loras && \
    # Install custom nodes (handle missing requirements gracefully)
    cd custom_nodes && \
    git clone --depth 1 https://github.com/mit-han-lab/ComfyUI-nunchaku nunchaku_nodes || echo  "nunchaku_nodes custom node clone failed, continuing..." && \
    if [ -d "nunchaku_nodes" ]; then \
        cd nunchaku_nodes && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "nunchaku_nodes requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for nunchaku_nodes custom node, skipping..."; \
        fi && \
        cd ..; \
    fi && \
    git clone --depth 1 https://github.com/rgthree/rgthree-comfy.git rgthree-comfy || echo "rgthree-comfy custom node clone failed, continuing..." && \
    if [ -d "rgthree-comfy" ]; then \
        cd rgthree-comfy && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "rgthree-comfy requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for rgthree-comfy custom node, skipping..."; \
        fi && \
        cd ..; \
    fi && \
    
    # Clean up
    find ${VENV_PATH} -name '__pycache__' -type d -exec rm -rf {} + && \
    pip cache purge

###############################################################################
# RUNTIME STAGE ###############################################################
###############################################################################
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_VERSION}

# Install runtime system dependencies including aria2c for fast downloads
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-dev git curl ca-certificates gpg tini aria2 \
        xz-utils && \
    \
    # Add repositories and install Caddy & Tailscale
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null && \
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | gpg --dearmor -o /usr/share/keyrings/tailscale-archive-keyring.gpg && \
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list > /dev/null && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends caddy tailscale && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built Python virtual environment and ComfyUI
ENV VENV_PATH=/opt/venv
COPY --from=builder ${VENV_PATH} ${VENV_PATH}
COPY --from=builder /workspace/ComfyUI /workspace/ComfyUI

# Copy configuration files
WORKDIR /workspace
COPY Caddyfile /etc/caddy/Caddyfile
COPY start_services_simple.sh /usr/local/bin/start_services.sh
COPY workflow_api.json /workspace/workflow_api.json
COPY api_wrapper.py /workspace/api_wrapper.py
COPY api_requirements.txt /workspace/api_requirements.txt
RUN chmod +x /usr/local/bin/start_services.sh

# Set environment variables optimized for RTX 4090 and network storage
ENV PATH="${VENV_PATH}/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    # RTX 4090 optimizations
    TORCH_INDUCTOR_FORCE_DISABLE_FP8="1" \
    CUDA_VISIBLE_DEVICES="0" \
    PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512" \
    # ComfyUI settings
    COMFY_DIR="/workspace/ComfyUI" \
    COMFY_LAUNCH_ARGS="--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto" \
    # Network storage settings
    MODELS_BASE_URL="https://huggingface.co" \
    ENABLE_FAST_DOWNLOAD="true"

# Expose ports
EXPOSE 8188 8189

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:8188/ || exit 1

# Use tini as the entrypoint to properly manage processes
ENTRYPOINT ["/usr/bin/tini", "-s", "--", "/usr/local/bin/start_services.sh"]