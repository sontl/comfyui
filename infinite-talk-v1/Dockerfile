# syntax=docker/dockerfile:1.7
###############################################################################
# INFINITE-TALK DOCKERFILE
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
    curl -L -o /tmp/sageattention.whl \
        https://huggingface.co/MonsterMMORPG/SECourses_Premium_Flash_Attention/resolve/main/sageattention-2.1.1-cp310-cp310-linux_x86_64.whl && \
    mv /tmp/sageattention.whl /tmp/sageattention-2.1.1-py3-none-any.whl && \
    pip install /tmp/sageattention-2.1.1-py3-none-any.whl && rm /tmp/sageattention-2.1.1-py3-none-any.whl && \
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
        librosa==0.10.2 \
        moviepy


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
    git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes.git comfyui-kjnodes || echo "KJNodes custom node clone failed, continuing..." && \
    if [ -d "comfyui-kjnodes" ]; then \
        cd comfyui-kjnodes && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "KJNodes requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for KJNodes custom node, skipping..."; \
        fi && \
        cd ..; \
    fi && \
    git clone --depth 1 https://github.com/kijai/ComfyUI-WanVideoWrapper.git || echo "WanVideoWrapper custom node clone failed, continuing..." && \
    if [ -d "ComfyUI-WanVideoWrapper" ]; then \
        cd ComfyUI-WanVideoWrapper && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "ComfyUI-WanVideoWrapper requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for ComfyUI-WanVideoWrapper custom node, skipping..."; \
        fi && \
        cd ..; \
    fi && \
    git clone --depth 1 https://github.com/orssorbit/ComfyUI-wanBlockswap.git wanBlockSwap || echo "wanBlockSwap custom node clone failed, continuing..." && \
    if [ -d "wanBlockSwap" ]; then \
        cd wanBlockSwap && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "wanBlockSwap requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for wanBlockSwap custom node, skipping..."; \
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
    git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git comfyui-videohelpersuite || echo "comfyui-videohelpersuite custom node clone failed, continuing..." && \
    if [ -d "comfyui-videohelpersuite" ]; then \
        cd comfyui-videohelpersuite && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "comfyui-videohelpersuite requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for comfyui-videohelpersuite custom node, skipping..."; \
        fi && \
        cd ..; \
    fi && \
    git clone --depth 1 https://github.com/stduhpf/ComfyUI-WanMoeKSampler WanMoeKSampler || echo "WanMoeKSampler custom node clone failed, continuing..." && \
    if [ -d "WanMoeKSampler" ]; then \
        cd WanMoeKSampler && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "WanMoeKSampler requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for WanMoeKSampler custom node, skipping..."; \
        fi; \
        cd ..; \
    fi && \
    git clone --depth 1 https://github.com/christian-byrne/audio-separation-nodes-comfyui.git audio-separation-nodes-comfyui || echo "audio-separation-nodes-comfyui custom node clone failed, continuing..." && \
    if [ -d "audio-separation-nodes-comfyui" ]; then \
        cd audio-separation-nodes-comfyui && \
        if [ -f "requirements.txt" ]; then \
            pip install --no-cache-dir -r requirements.txt || echo "audio-separation-nodes-comfyui requirements install failed, continuing..."; \
        else \
            echo "No requirements.txt found for audio-separation-nodes-comfyui custom node, skipping..."; \
        fi; \
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
    # Install static ffmpeg build with NVIDIA codec support
    cd /tmp && \
    curl -L https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -o ffmpeg.tar.xz && \
    tar -xf ffmpeg.tar.xz && \
    cp ffmpeg-master-latest-linux64-gpl/bin/ffmpeg /usr/local/bin/ffmpeg && \
    cp ffmpeg-master-latest-linux64-gpl/bin/ffprobe /usr/local/bin/ffprobe && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    rm -rf /tmp/ffmpeg* && \
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