#!/usr/bin/env bash
set -u

# Simple, robust startup script for FastWAN 2.2-5B
VENV_COMFY=${VENV_COMFY:-/opt/venv}
COMFY_DIR="/workspace/ComfyUI"
COMFY_LAUNCH_ARGS=${COMFY_LAUNCH_ARGS:-"--listen 0.0.0.0 --port 8188 --disable-auto-launch --preview-method auto"}

# Model URLs
DIFFUSION_MODEL_URL="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
TEXT_ENCODER_URL="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
VAE_URL="https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors"
LORA_URL="https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/FastWan/Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors"

log() {
    echo "[$(date '+%H:%M:%S')] $*"
}

# Prevent multiple instances
if [ -f "/tmp/fastwan.lock" ]; then
    log "Another instance is running. Exiting."
    exit 0
fi
echo $$ > /tmp/fastwan.lock
trap "rm -f /tmp/fastwan.lock" EXIT

log "=== FastWAN 2.2-5B Simple Startup ==="

# Step 1: Setup ComfyUI
log "Step 1: Setting up ComfyUI..."

# Remove any existing broken directory
if [ -d "${COMFY_DIR}" ] && [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "Removing broken ComfyUI directory..."
    rm -rf "${COMFY_DIR}"
fi

# Clone ComfyUI if needed
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "Cloning ComfyUI..."
    git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git "${COMFY_DIR}" || {
        log "Git clone failed. Trying alternative method..."
        rm -rf "${COMFY_DIR}"
        mkdir -p /tmp/comfy_clone
        cd /tmp/comfy_clone
        git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git . && {
            mv /tmp/comfy_clone "${COMFY_DIR}"
            log "ComfyUI cloned via alternative method."
        } || {
            log "FATAL: Cannot clone ComfyUI"
            exit 1
        }
    }
else
    log "ComfyUI already exists."
fi

# Verify ComfyUI
if [ ! -f "${COMFY_DIR}/main.py" ]; then
    log "FATAL: ComfyUI main.py not found after setup"
    exit 1
fi

cd "${COMFY_DIR}"

# Install requirements
if [ -f "requirements.txt" ]; then
    log "Installing ComfyUI requirements..."
    source "${VENV_COMFY}/bin/activate"
    pip install --no-cache-dir -r requirements.txt > /dev/null 2>&1 || log "Warning: Requirements install failed"
    deactivate
fi

# Step 2: Setup custom nodes
log "Step 2: Setting up FastWAN custom node..."
if [ ! -d "custom_nodes/fastwan-moviegen" ]; then
    log "Cloning FastWAN custom node..."
    git clone --depth 1 https://github.com/FNGarvin/fastwan-moviegen.git custom_nodes/fastwan-moviegen > /dev/null 2>&1 || \
        log "Warning: Failed to clone FastWAN custom node"
fi

if [ -d "custom_nodes/fastwan-moviegen" ] && [ -f "custom_nodes/fastwan-moviegen/requirements.txt" ]; then
    log "Installing FastWAN custom node requirements..."
    source "${VENV_COMFY}/bin/activate"
    cd custom_nodes/fastwan-moviegen
    pip install --no-cache-dir -r requirements.txt > /dev/null 2>&1 || log "Warning: FastWAN requirements install failed"
    cd "${COMFY_DIR}"
    deactivate
fi

# Step 3: Download models
log "Step 3: Downloading models..."

download_model() {
    local url="$1"
    local path="$2"
    local dir=$(dirname "$path")
    
    mkdir -p "$dir"
    
    if [ -f "$path" ]; then
        log "Model already exists: $(basename "$path")"
        return 0
    fi
    
    log "Downloading $(basename "$path")..."
    if command -v aria2c > /dev/null 2>&1; then
        aria2c -x 16 -s 16 --dir="$dir" -o "$(basename "$path")" "$url" > /dev/null 2>&1 || {
            log "aria2c failed, using curl..."
            curl -L -o "$path" "$url" > /dev/null 2>&1
        }
    else
        curl -L -o "$path" "$url" > /dev/null 2>&1
    fi
    
    if [ -f "$path" ]; then
        log "Downloaded: $(basename "$path")"
    else
        log "Failed to download: $(basename "$path")"
        return 1
    fi
}

# Download all models
download_model "$DIFFUSION_MODEL_URL" "${COMFY_DIR}/models/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors"
download_model "$TEXT_ENCODER_URL" "${COMFY_DIR}/models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"
download_model "$VAE_URL" "${COMFY_DIR}/models/vae/wan2.2_vae.safetensors"
download_model "$LORA_URL" "${COMFY_DIR}/models/loras/Wan2_2_5B_FastWanFullAttn_lora_rank_128_bf16.safetensors"

# Step 4: Start services
log "Step 4: Starting services..."

# Set environment variables
export TORCH_INDUCTOR_FORCE_DISABLE_FP8="1"
export CUDA_VISIBLE_DEVICES="0"
export PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:512"

source "${VENV_COMFY}/bin/activate"

# Copy workflow file
cp /workspace/workflow_api.json "${COMFY_DIR}/" 2>/dev/null || true

# Start API wrapper
log "Starting API wrapper..."
cd /workspace
python3 api_wrapper.py &
API_PID=$!
log "API wrapper started (PID: $API_PID)"

# Start ComfyUI
log "Starting ComfyUI..."
cd "${COMFY_DIR}"
python main.py ${COMFY_LAUNCH_ARGS} &
COMFY_PID=$!
log "ComfyUI started (PID: $COMFY_PID)"

deactivate

# Start Caddy
if [ -f "/etc/caddy/Caddyfile" ]; then
    log "Starting Caddy..."
    caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
    CADDY_PID=$!
    log "Caddy started (PID: $CADDY_PID)"
fi

# Setup cleanup
cleanup() {
    log "Shutting down services..."
    [ -n "${API_PID:-}" ] && kill -TERM "$API_PID" 2>/dev/null || true
    [ -n "${COMFY_PID:-}" ] && kill -TERM "$COMFY_PID" 2>/dev/null || true
    [ -n "${CADDY_PID:-}" ] && kill -TERM "$CADDY_PID" 2>/dev/null || true
    sleep 5
    [ -n "${API_PID:-}" ] && kill -KILL "$API_PID" 2>/dev/null || true
    [ -n "${COMFY_PID:-}" ] && kill -KILL "$COMFY_PID" 2>/dev/null || true
    [ -n "${CADDY_PID:-}" ] && kill -KILL "$CADDY_PID" 2>/dev/null || true
    log "Shutdown complete."
    exit 0
}

trap cleanup SIGTERM SIGINT

log "=== Startup Complete ==="
log "ComfyUI: http://localhost:8188"
log "API: http://localhost:8189"
log "API Docs: http://localhost:8189/docs"

# Wait for services
if [ -n "${COMFY_PID:-}" ] && [ -n "${API_PID:-}" ]; then
    wait -n "$COMFY_PID" "$API_PID"
    log "A service exited. Shutting down..."
    cleanup
else
    log "No services started. Exiting."
    exit 1
fi