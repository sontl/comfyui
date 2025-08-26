# syntax=docker/dockerfile:1.7
###############################################################################
# BUILD STAGE #################################################################
###############################################################################
ARG CUDA_VERSION=12.6.0
ARG UBUNTU_VERSION=22.04
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_VERSION} AS builder

# --- base tooling -----------------------------------------------------------
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-venv python3-distutils python3-pip \
        build-essential git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# --- Python venv & Core ML stack ---------------------------------------------
ARG TORCH_CUDA=cu126
ARG TORCH_VER=2.6.0
ARG TVISION_VER=0.21.0+${TORCH_CUDA}
ARG TAUDIO_VER=2.6.0+${TORCH_CUDA}
ARG XFORMERS_VER=0.0.29.post2

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

###############################################################################
# RUNTIME STAGE ###############################################################
###############################################################################
FROM nvidia/cuda:${CUDA_VERSION}-cudnn-devel-ubuntu${UBUNTU_VERSION}

# Install runtime system dependencies
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-dev git curl ca-certificates gpg ffmpeg tini && \
    \
    # Add repositories and install Caddy & Tailscale
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null && \
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.noarmor.gpg | gpg --dearmor -o /usr/share/keyrings/tailscale-archive-keyring.gpg && \
    curl -fsSL https://pkgs.tailscale.com/stable/ubuntu/jammy.tailscale-keyring.list | tee /etc/apt/sources.list.d/tailscale.list > /dev/null && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends caddy tailscale && \
    rm -rf /var/lib/apt/lists/*

# Copy the pre-built Python virtual environment
ENV VENV_PATH=/opt/venv
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Copy configuration and startup script
WORKDIR /workspace
COPY Caddyfile /etc/caddy/Caddyfile
COPY start_services.sh /usr/local/bin/start_services.sh
RUN chmod +x /usr/local/bin/start_services.sh

# Set environment variables for the container runtime
ENV PATH="${VENV_PATH}/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    # THIS IS THE FIX: Disable FP8 compilation for Ampere compatibility
    TORCH_INDUCTOR_FORCE_DISABLE_FP8="1"

# Use tini as the entrypoint to properly manage processes
ENTRYPOINT ["/usr/bin/tini", "-s", "--", "/usr/local/bin/start_services.sh"]